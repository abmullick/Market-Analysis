"""Bond Central credit-ratings index synchronization.

Walks the Bond Central securities API page by page (``?page=N&size=100``) —
using the API's own pagination metadata, never one request per ISIN — keeps
only rating information, and stores it in the persistent ratings index
(:mod:`backend.services.bonds.bond_central_ratings_index`).

The index is refreshed independently of bond list/detail requests:

* ``refresh()`` performs a full sweep and atomically replaces the index on
  success. Partial sweeps keep the last good snapshot and are reported as
  ``partial`` together with the underlying error.
* ``maybe_schedule_refresh()`` schedules a background sweep when the index is
  stale. It never blocks a request and refuses to run inside a test process.

Failures are contained: HTTP errors, timeouts, invalid payloads and HTTP 429
rate limiting are retried with backoff (honouring ``Retry-After``) and reported
through the index metadata instead of raising into request handling. A
persistently failing size=100 window is split into 2x size=50 (then 2x
size=25) so server-side poison records cost only their own sub-window.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

from backend.models.bonds import BondCentralRating, BondCentralRawRating
from backend.services.bonds.bond_central_ratings_index import (
    META_DURATION_SECONDS,
    META_ERROR,
    META_LAST_ATTEMPT,
    META_LAST_SUCCESS,
    META_PAGES_FAILED,
    META_PAGES_FETCHED,
    META_RATINGS_STORED,
    META_RECORDS_PROCESSED,
    META_SECURITIES_INDEXED,
    META_STATUS,
    META_TOTAL_PAGES,
    RATING_STATUS_RATED,
    RATING_STATUS_UNKNOWN,
    RATING_STATUS_UNRATED,
    get_ratings_index,
    normalize_isin,
)
from backend.services.data.bonds.bond_central import (
    BondCentralClient,
    BondCentralFetchError,
    BondCentralRateLimited,
)
from backend.utils.logging import logger

#: The API caps ``size`` at 100.
PAGE_SIZE = 100

#: Safety bound on the sweep (the API reports ~25.5k records => ~256 pages).
MAX_PAGES = 500

_MAX_RETRY_AFTER_SECONDS = 30.0

#: Per-page retry policy for transient failures (e.g. HTTP 500 on pages
#: 19/42/200/209/239/253): at most 3 retries with exponential backoff.
_MAX_PAGE_RETRIES = 3
_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (2.0, 5.0, 10.0)

#: Max characters of a response body kept in persistent-failure diagnostics.
_BODY_EXCERPT_LIMIT = 500

#: Split-recovery fallback for poison records: when a size=100 window
#: persistently fails (server-side HTTP 500 caused by a corrupt record in the
#: window), the same offset range is re-fetched as 2x size=50, and a still
#: failing half as 2x size=25. Size=25 windows are never split further.
_RECOVERY_HALF_SIZE = 50
_RECOVERY_QUARTER_SIZE = 25

#: Minimum spacing between two automatically triggered sweeps.
MIN_AUTO_REFRESH_INTERVAL_SECONDS = 300.0

_STATUS_RANK = {
    RATING_STATUS_UNRATED: 0,
    RATING_STATUS_UNKNOWN: 1,
    RATING_STATUS_RATED: 2,
}


def _rating_signature(row: BondCentralRawRating) -> tuple:
    return (
        row.credit_rating,
        row.credit_rating_agency_name,
        row.date_of_credit_rating,
        row.ratings_watch,
        row.ratings_outlook,
    )


def _has_rating_metadata(row: BondCentralRawRating) -> bool:
    return bool(
        row.credit_rating_agency_name
        or row.date_of_credit_rating
        or row.ratings_watch
        or row.ratings_outlook
    )


def _failure_status(exc: BaseException) -> Any:
    """Best-effort HTTP status carried by a page-fetch failure."""
    return getattr(exc, "status_code", "unknown")


def _failure_body(exc: BaseException) -> str:
    """Normalized body excerpt carried by a page-fetch failure."""
    body = getattr(exc, "body_excerpt", None)
    if body is None:
        return "-"
    text = " ".join(str(body).split())
    excerpt = text[:_BODY_EXCERPT_LIMIT]
    return excerpt or "-"


def _failure_detail(page: int, exc: BaseException) -> str:
    """Persistent-failure detail: page number, HTTP status and body excerpt."""
    return (
        f"page {page}: HTTP {_failure_status(exc)}: {exc}; "
        f"body={_failure_body(exc)}"
    )


def _retry_delay_seconds(retry_index: int) -> float:
    """Exponential backoff delay for a 0-based retry index (2s, 5s, 10s)."""
    if retry_index < len(_RETRY_BACKOFF_SECONDS):
        return _RETRY_BACKOFF_SECONDS[retry_index]
    return _RETRY_BACKOFF_SECONDS[-1]


def _recovery_sub_page(page: int, size: int, half_index: int) -> int:
    """1-based sub-page covering half ``half_index`` (0/1) of a ``size`` window."""
    half = size // 2
    return (page - 1) * (size // half) + half_index + 1


def _recovery_offset(page: int, size: int) -> int:
    """0-based record offset of a (page, size) window."""
    return (page - 1) * size


def _recovery_detail(
    page: int,
    page_size: int,
    sub_page: int,
    sub_size: int,
    exc: BaseException,
) -> str:
    """Diagnostic for an irretrievable sub-window of a split page."""
    offset = _recovery_offset(sub_page, sub_size)
    return (
        f"page {page} (size={page_size}, offset={_recovery_offset(page, page_size)}): "
        f"sub-window page {sub_page} size={sub_size} offset={offset} "
        f"persistently failed: HTTP {_failure_status(exc)}: {exc}; "
        f"body={_failure_body(exc)}"
    )


def _to_rating(row: BondCentralRawRating) -> BondCentralRating:
    """Map a raw row onto the rating record exposed through the API.

    Only rating information is retained; Bond Central security details
    (maturity, security name, issuer) are deliberately dropped.
    """
    return BondCentralRating(
        credit_rating=row.credit_rating,
        credit_rating_agency_name=row.credit_rating_agency_name,
        date_of_credit_rating=row.date_of_credit_rating,
        ratings_watch=row.ratings_watch,
        ratings_outlook=row.ratings_outlook,
        security_status=row.security_status,
    )


class BondCentralRatingsSync:
    """Full-index synchronization service for Bond Central credit ratings."""

    def __init__(
        self,
        settings: Any = None,
        index: Any = None,
        client: Optional[BondCentralClient] = None,
    ) -> None:
        if settings is None:
            from backend.config.settings import Settings

            settings = Settings()
        self._settings = settings
        self._index = index if index is not None else get_ratings_index(settings)
        self._client = client
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._last_attempt_at = 0.0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def index(self) -> Any:
        return self._index

    @property
    def ttl_seconds(self) -> int:
        return int(
            getattr(self._settings, "bond_central_ratings_ttl_seconds", 86400)
        )

    @property
    def page_delay_seconds(self) -> float:
        try:
            return max(
                0.0,
                float(
                    getattr(
                        self._settings,
                        "bond_central_ratings_page_delay_seconds",
                        0.2,
                    )
                ),
            )
        except (TypeError, ValueError):
            return 0.2

    @property
    def max_retries(self) -> int:
        try:
            return max(
                0,
                min(
                    int(
                        getattr(
                            self._settings,
                            "bond_central_ratings_max_retries",
                            _MAX_PAGE_RETRIES,
                        )
                    ),
                    _MAX_PAGE_RETRIES,
                ),
            )
        except (TypeError, ValueError):
            return _MAX_PAGE_RETRIES

    @property
    def auto_refresh_enabled(self) -> bool:
        return bool(
            getattr(self._settings, "bond_central_ratings_auto_refresh", True)
        )

    def _get_client(self) -> BondCentralClient:
        if self._client is None:
            self._client = BondCentralClient(self._settings)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()

    # ------------------------------------------------------------------
    # State / scheduling
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def is_stale(self) -> bool:
        return bool(self._index.metadata().get("stale", True))

    def status(self) -> dict[str, Any]:
        """Current index metadata plus the live running flag."""
        meta = self._index.metadata()
        meta["running"] = self.is_running()
        return meta

    def schedule_refresh(self, reason: str = "manual") -> bool:
        """Schedule a background sweep; ``False`` when one is already running.

        Used by the explicit refresh endpoint, so it is not gated on staleness
        or on the test-process guard.
        """
        try:
            if self.is_running():
                return False
            loop = asyncio.get_running_loop()
        except Exception:  # no running loop
            return False
        self._last_attempt_at = time.time()
        self._task = loop.create_task(self._run_background(reason))
        return True

    def maybe_schedule_refresh(self, reason: str = "auto") -> bool:
        """Schedule a background sweep when the index is stale.

        Never blocks and never raises: request handling must not depend on
        Bond Central availability, and tests must never trigger live provider
        traffic.
        """
        try:
            if not self.auto_refresh_enabled or self.is_running():
                return False
            if not self.is_stale():
                return False
            if time.time() - self._last_attempt_at < MIN_AUTO_REFRESH_INTERVAL_SECONDS:
                return False
            if os.environ.get("PYTEST_CURRENT_TEST"):
                return False
            asyncio.get_running_loop()
        except Exception:  # diagnostics only
            return False
        return self.schedule_refresh(reason)

    async def _run_background(self, reason: str) -> None:
        try:
            await self.refresh(reason=reason)
        except Exception as exc:  # never surface into a request
            logger.warning("Bond Central ratings background refresh failed: %s", exc)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    async def refresh(self, reason: str = "manual") -> dict[str, Any]:
        """Sweep every Bond Central page and rebuild the ratings index.

        Returns the resulting index metadata. The index is replaced only when
        every page was retrieved; a partial or failed sweep keeps the previous
        snapshot and records the failure in the metadata.
        """
        async with self._lock:
            return await self._refresh_locked(reason)

    async def _refresh_locked(self, reason: str) -> dict[str, Any]:
        started = time.time()
        self._last_attempt_at = started
        logger.info("Bond Central ratings index refresh started (%s)", reason)
        self._index.update_metadata(
            **{
                META_STATUS: "running",
                META_LAST_ATTEMPT: started,
                META_ERROR: None,
                META_PAGES_FETCHED: 0,
                META_PAGES_FAILED: 0,
            }
        )

        ratings_by_isin: dict[str, list[BondCentralRating]] = {}
        statuses: dict[str, str] = {}
        seen: dict[str, set[tuple]] = {}
        errors: list[str] = []
        pages_fetched = 0
        pages_failed = 0
        records_processed = 0
        total_pages: Optional[int] = None
        page = 1

        try:
            while page <= MAX_PAGES:
                try:
                    rows, info = await self._fetch_page_with_retry(page)
                except BondCentralFetchError as exc:
                    pages_failed += 1
                    detail = _failure_detail(page, exc)
                    errors.append(detail)
                    logger.warning(
                        "Bond Central ratings page %d failed "
                        "(status=%s): %s; body=%s",
                        page,
                        _failure_status(exc),
                        exc,
                        _failure_body(exc),
                    )
                    if page == 1:
                        break
                    page += 1
                    continue

                pages_fetched += 1
                records_processed += len(rows)
                if isinstance(info.get("total_pages"), int):
                    total_pages = info["total_pages"]
                recovery_warning = info.get("_recovery_warnings")
                if recovery_warning is not None:
                    errors.append(
                        f"page {page} partially recovered: {recovery_warning}"
                    )
                    logger.warning(
                        "Bond Central ratings page %d partially recovered: %s",
                        page,
                        recovery_warning,
                    )
                self._accumulate(rows, ratings_by_isin, statuses, seen)

                if not rows:
                    break
                if info.get("has_next") is False:
                    break
                if total_pages is not None and page >= total_pages:
                    break

                page += 1
                if pages_fetched % 10 == 0:
                    self._index.update_metadata(
                        **{
                            META_PAGES_FETCHED: pages_fetched,
                            META_PAGES_FAILED: pages_failed,
                            META_RECORDS_PROCESSED: records_processed,
                            META_TOTAL_PAGES: total_pages,
                        }
                    )
                if self.page_delay_seconds:
                    await asyncio.sleep(self.page_delay_seconds)
        finally:
            self._finish_refresh(
                reason=reason,
                started=started,
                pages_fetched=pages_fetched,
                pages_failed=pages_failed,
                records_processed=records_processed,
                total_pages=total_pages,
                ratings_by_isin=ratings_by_isin,
                statuses=statuses,
                errors=errors,
            )

        return self.status()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _finish_refresh(
        self,
        *,
        reason: str,
        started: float,
        pages_fetched: int,
        pages_failed: int,
        records_processed: int,
        total_pages: Optional[int],
        ratings_by_isin: dict[str, list[BondCentralRating]],
        statuses: dict[str, str],
        errors: list[str],
    ) -> None:
        """Persist the sweep outcome (success / partial / error)."""
        duration = round(time.time() - started, 1)
        if pages_fetched == 0:
            error = "; ".join(errors) or "no Bond Central page could be retrieved"
            self._index.update_metadata(
                **{
                    META_STATUS: "error",
                    META_ERROR: error[:1000],
                    META_PAGES_FETCHED: 0,
                    META_PAGES_FAILED: pages_failed,
                    META_DURATION_SECONDS: duration,
                }
            )
            logger.warning(
                "Bond Central ratings refresh failed (%s): %s", reason, error
            )
            return

        if not statuses:
            # Paged responses arrived but held no securities: unusable sweep.
            # Keep the previous index rather than wiping it.
            self._index.update_metadata(
                **{
                    META_STATUS: "error",
                    META_ERROR: (
                        "Bond Central returned no securities "
                        f"({pages_fetched} page(s) fetched)"
                    ),
                    META_PAGES_FETCHED: pages_fetched,
                    META_PAGES_FAILED: pages_failed,
                    META_RECORDS_PROCESSED: records_processed,
                    META_TOTAL_PAGES: total_pages,
                    META_DURATION_SECONDS: duration,
                }
            )
            logger.warning(
                "Bond Central ratings refresh unusable (%s): no securities in "
                "%d page(s); previous index kept",
                reason,
                pages_fetched,
            )
            return

        if pages_failed or errors:
            # Partial sweep: report it and keep the last complete snapshot.
            self._index.update_metadata(
                **{
                    META_STATUS: "partial",
                    META_ERROR: "; ".join(errors)[:1000],
                    META_PAGES_FETCHED: pages_fetched,
                    META_PAGES_FAILED: pages_failed,
                    META_RECORDS_PROCESSED: records_processed,
                    META_TOTAL_PAGES: total_pages,
                    META_DURATION_SECONDS: duration,
                }
            )
            logger.warning(
                "Bond Central ratings refresh partial (%s): %d page(s) failed; "
                "previous index kept",
                reason,
                pages_failed,
            )
            return

        ratings_stored = sum(len(rows) for rows in ratings_by_isin.values())
        self._index.replace_snapshot(
            ratings_by_isin,
            statuses,
            {
                META_STATUS: "ok",
                META_LAST_SUCCESS: time.time(),
                META_ERROR: None,
                META_RECORDS_PROCESSED: records_processed,
                META_RATINGS_STORED: ratings_stored,
                META_SECURITIES_INDEXED: len(statuses),
                META_PAGES_FETCHED: pages_fetched,
                META_PAGES_FAILED: 0,
                META_TOTAL_PAGES: total_pages,
                META_DURATION_SECONDS: duration,
            },
        )
        logger.info(
            "Bond Central ratings refresh complete (%s): %d record(s) processed, "
            "%d rating row(s), %d ISIN(s) indexed in %.1fs",
            reason,
            records_processed,
            ratings_stored,
            len(statuses),
            duration,
        )

    @staticmethod
    def _accumulate(
        rows: list[BondCentralRawRating],
        ratings_by_isin: dict[str, list[BondCentralRating]],
        statuses: dict[str, str],
        seen: dict[str, set[tuple]],
    ) -> None:
        """Fold one page of raw rows into the ISIN-keyed index maps.

        Handles null ratings, missing/empty ratings arrays, duplicate ISINs and
        multiple rating agencies: every distinct rating row is kept, and the
        strongest coverage status seen for an ISIN wins.
        """
        grouped: dict[str, list[BondCentralRawRating]] = {}
        for row in rows:
            isin = normalize_isin(getattr(row, "isin", None))
            if isin:
                grouped.setdefault(isin, []).append(row)

        for isin, group in grouped.items():
            has_rating = any(row.credit_rating for row in group)
            has_metadata = any(_has_rating_metadata(row) for row in group)
            if has_rating:
                status = RATING_STATUS_RATED
            elif has_metadata:
                status = RATING_STATUS_UNKNOWN
            else:
                status = RATING_STATUS_UNRATED
            previous = statuses.get(isin)
            if previous is None or _STATUS_RANK[status] > _STATUS_RANK[previous]:
                statuses[isin] = status

            signatures = seen.setdefault(isin, set())
            bucket = ratings_by_isin.setdefault(isin, [])
            for row in group:
                if not (row.credit_rating or _has_rating_metadata(row)):
                    continue  # entry carries no rating information at all
                signature = _rating_signature(row)
                if signature in signatures:
                    continue  # duplicate ISIN/rating row
                signatures.add(signature)
                bucket.append(_to_rating(row))
            if not bucket:
                ratings_by_isin.pop(isin, None)

    async def _fetch_page_with_retry(
        self,
        page: int,
    ) -> tuple[list[BondCentralRawRating], dict[str, Any]]:
        """Fetch one page, retrying rate limits and transient failures.

        At most 3 retries per page with exponential backoff (2s, 5s, 10s).
        HTTP 500 and other fetch errors are retried; when the size=100
        window still fails, it is split into 2x size=50 (and a failing half
        into 2x size=25) so poison records cost only their own sub-window.
        Callers keep sweeping later pages when a page still fails, and the
        snapshot is replaced only when every page succeeded.
        """
        try:
            return await self._fetch_one(page, PAGE_SIZE)
        except BondCentralFetchError as exc:
            if PAGE_SIZE == _RECOVERY_HALF_SIZE * 2:
                recovered = await self._recover_split_page(page, exc)
                if recovered is not None:
                    return recovered
            raise

    async def _fetch_one(
        self,
        page: int,
        size: int,
    ) -> tuple[list[BondCentralRawRating], dict[str, Any]]:
        """Fetch one (page, size) window with the existing retry policy."""
        attempts = self.max_retries
        last_exc: Optional[BondCentralFetchError] = None
        for attempt in range(attempts + 1):
            try:
                return await self._get_client().fetch_securities_page(
                    page, size
                )
            except BondCentralRateLimited as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                delay = (
                    exc.retry_after
                    if exc.retry_after
                    else _retry_delay_seconds(attempt)
                )
                delay = min(max(float(delay), 0.0), _MAX_RETRY_AFTER_SECONDS)
                logger.info(
                    "Bond Central rate limited on page %d size=%d; "
                    "retrying in %.1fs (attempt %d/%d)",
                    page,
                    size,
                    delay,
                    attempt + 1,
                    attempts,
                )
                await asyncio.sleep(delay)
            except BondCentralFetchError as exc:
                last_exc = exc
                if attempt >= attempts:
                    break
                delay = _retry_delay_seconds(attempt)
                logger.info(
                    "Bond Central page %d size=%d failed (status=%s): %s; "
                    "retrying in %.1fs (attempt %d/%d)",
                    page,
                    size,
                    _failure_status(exc),
                    exc,
                    delay,
                    attempt + 1,
                    attempts,
                )
                await asyncio.sleep(delay)

        if last_exc is not None:
            raise last_exc
        raise BondCentralFetchError(
            f"page {page} size={size}: retries exhausted"
        )

    async def _recover_split_page(
        self,
        page: int,
        exc: BondCentralFetchError,
    ) -> Optional[tuple[list[BondCentralRawRating], dict[str, Any]]]:
        """Split a persistently failed size=100 window into smaller reads."""
        logger.info(
            "Bond Central page %d failed persistently (status=%s); "
            "splitting into 2x size=%d",
            page,
            _failure_status(exc),
            _RECOVERY_HALF_SIZE,
        )
        halves: list[tuple[list[BondCentralRawRating], dict[str, Any]]] = []
        diagnostics: list[str] = []
        for half_index in range(2):
            sub_page = _recovery_sub_page(page, PAGE_SIZE, half_index)
            try:
                halves.append(
                    await self._fetch_one(sub_page, _RECOVERY_HALF_SIZE)
                )
                continue
            except BondCentralFetchError:
                pass
            recovered_half = await self._recover_half_page(
                page, sub_page, diagnostics
            )
            if recovered_half is not None:
                halves.append(recovered_half)
        if not halves and not diagnostics:
            return None
        if not halves:
            raise BondCentralFetchError(
                f"page {page}: unrecoverable after split; "
                + "; ".join(diagnostics),
                status_code=_failure_status(exc),
                body_excerpt=getattr(exc, "body_excerpt", None),
            ) from exc
        rows = [row for window, _ in halves for row in window]
        info = dict(halves[0][1])
        if diagnostics:
            chained: Any = BondCentralFetchError(
                "; ".join(diagnostics),
                status_code=_failure_status(exc),
                body_excerpt=getattr(exc, "body_excerpt", None),
            )
            chained.__cause__ = exc
            info["_recovery_warnings"] = chained
        return rows, info

    async def _recover_half_page(
        self,
        page: int,
        sub_page: int,
        diagnostics: list[str],
    ) -> Optional[tuple[list[BondCentralRawRating], dict[str, Any]]]:
        """Split one failed size=50 half into 2x size=25 windows."""
        quarters: list[tuple[list[BondCentralRawRating], dict[str, Any]]] = []
        for quarter_index in range(2):
            quarter_page = _recovery_sub_page(
                sub_page, _RECOVERY_HALF_SIZE, quarter_index
            )
            try:
                quarters.append(
                    await self._fetch_one(
                        quarter_page, _RECOVERY_QUARTER_SIZE
                    )
                )
            except BondCentralFetchError as quarter_exc:
                detail = _recovery_detail(
                    page, PAGE_SIZE, quarter_page,
                    _RECOVERY_QUARTER_SIZE, quarter_exc,
                )
                diagnostics.append(detail)
                logger.warning("Bond Central %s", detail)
        if not quarters:
            return None
        rows = [row for window, _ in quarters for row in window]
        return rows, dict(quarters[0][1])
