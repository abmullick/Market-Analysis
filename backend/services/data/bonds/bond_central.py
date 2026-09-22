"""Bond Central securities / credit-ratings adapter (public JSON API).

Source (official public API, one ISIN per request):

    GET https://api.bondcentral.in/securities/?isin={ISIN}&page=1&size=10

This adapter is used as an ADDITIONAL corporate-bond credit-rating source.
It does not scrape the Bond Central website, requires no API key, and does
not use any paid/commercial vendor.

Fields extracted per security row (the API nests them as
``data[].data.ratings[]`` with ``cra_rating``; flat shapes are also
accepted defensively):
    cra_rating                  -> credit_rating
    credit_rating_agency_name   -> credit_rating_agency_name
    date_of_credit_rating       -> date_of_credit_rating
    ratings_watch               -> ratings_watch
    ratings_outlook             -> ratings_outlook
    security_status             -> security_status
    maturity_date               -> maturity_date

Multiple rows are preserved so several ratings for the same ISIN are not
collapsed. Only fields genuinely present in the payload are populated;
absent fields stay ``None`` per model convention. No values are invented.

Failure policy: timeout, HTTP error, empty response, malformed JSON, or an
unexpected payload shape yields an empty list so the Bond service layer can
continue without ratings. Government securities, T-Bills and SDLs are not
CRA-rated and are never queried here.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from backend.config.settings import Settings
from backend.models.bonds import BondCentralRawRating
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# Bond Central public securities API
# ---------------------------------------------------------------------------

BOND_CENTRAL_BASE = "https://api.bondcentral.in"
BOND_CENTRAL_SECURITIES_URL = f"{BOND_CENTRAL_BASE}/securities/"

# One ISIN per request; the endpoint is paginated (page/size).
_REQUEST_PAGE = 1
_REQUEST_SIZE = 10

#: The API rejects ``size`` values above 100 (HTTP 422).
_MAX_PAGE_SIZE = 100

# Public JSON API — no cookie/session priming is required.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Values the source uses as "not supplied" sentinels.
_MISSING = {
    "", "-", "--", "N/A", "NA", "n/a", "null", "none", "None",
    "Not Applicable", "Not applicable", "NOT APPLICABLE",
    "Not Available", "Not available", "Not Rated", "Unrated", "unrated",
}


def _clean(value: Any) -> Optional[str]:
    """Normalize a source value to a trimmed string or ``None``.

    Missing sentinels, blanks and null bytes are treated as absent so they
    are never displayed as if they were real rating data.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    s = value.replace(chr(0), "").strip()
    if not s or s in _MISSING:
        return None
    return s


def _first(row: dict, *keys: str) -> Any:
    """Return the first present, non-empty value among *keys*."""
    for key in keys:
        if key in row:
            value = row[key]
            if value is not None and value != "":
                return value
    return None


def _rows(payload: Any) -> list[dict]:
    """Locate the list of security rows inside the API payload.

    Bond Central wraps its results in an envelope whose key is not
    contractual; several common shapes are accepted defensively. A bare
    list or a single-object payload is also accepted.
    """
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("results", "data", "securities", "items", "result", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        # A single security object may be wrapped directly under "data".
        value = payload.get("data")
        if isinstance(value, dict):
            return [value]
        if any(k in payload for k in ("credit_rating", "isin", "ISIN")):
            return [payload]
    return []


def _security_payload(row: dict) -> dict:
    """Return the security object from one API row.

    Bond Central nests the security fields under a ``data`` key::

        {"isin": "...", "data": {..., "ratings": [...]}}

    A flat row is accepted defensively.
    """
    if not isinstance(row, dict):
        return {}
    inner = row.get("data")
    return inner if isinstance(inner, dict) else row


class BondCentralFetchError(RuntimeError):
    """Raised when a Bond Central securities page cannot be retrieved."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Any = None,
        body_excerpt: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body_excerpt = body_excerpt


class BondCentralRateLimited(BondCentralFetchError):
    """Raised when Bond Central throttles the client (HTTP 429)."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        *,
        status_code: Any = 429,
        body_excerpt: Any = None,
    ) -> None:
        super().__init__(
            message, status_code=status_code, body_excerpt=body_excerpt
        )
        self.retry_after = retry_after


def _body_excerpt(response: Any, limit: int = 500) -> Optional[str]:
    """Best-effort excerpt of an HTTP response body for diagnostics."""
    if response is None:
        return None
    try:
        body: Any = getattr(response, "text", None)
        if not isinstance(body, str):
            content = getattr(response, "content", None)
            if isinstance(content, (bytes, bytearray)):
                body = bytes(content).decode("utf-8", errors="replace")
            elif content is not None:
                body = str(content)
            else:
                return None
        if not body:
            return None
        excerpt = " ".join(str(body).split())
        return excerpt[:limit] or None
    except Exception:
        return None


def _retry_after_seconds(response: Any) -> Optional[float]:
    """Best-effort parse of a ``Retry-After`` header (seconds)."""
    try:
        raw = response.headers.get("Retry-After")
    except AttributeError:
        return None
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        return None


def _pagination_info(payload: Any) -> dict[str, Any]:
    """Return the API's ``pagination_info`` object (empty when absent)."""
    if isinstance(payload, dict) and isinstance(payload.get("pagination_info"), dict):
        return dict(payload["pagination_info"])
    return {}


def _rating_entries(security: dict) -> list[dict]:
    """Return the rating entries for one security.

    Ratings live in the security's ``ratings`` list and each entry carries
    ``cra_rating``. A flat security object is treated as a single entry so
    the legacy shape keeps working.
    """
    ratings = security.get("ratings")
    if isinstance(ratings, list):
        return [entry for entry in ratings if isinstance(entry, dict)]
    return [security]


def _extract_rows(security: dict) -> list[BondCentralRawRating]:
    """Map one Bond Central security payload into rating records.

    One record is produced per rating entry so multiple ratings for the same
    ISIN are preserved. Security-level fields (status, maturity) are carried
    on every record.
    """
    isin = _clean(_first(security, "isin", "ISIN"))
    security_status = _clean(_first(security, "security_status", "status"))
    maturity_date = _clean(_first(security, "maturity_date", "date_of_maturity"))
    security_name = _clean(
        _first(
            security,
            "security_name",
            "security_description",
            "isin_description",
            "name",
        )
    )
    issuer_name = _clean(_first(security, "issuer", "issuer_name"))

    records: list[BondCentralRawRating] = []
    for entry in _rating_entries(security):
        credit_rating = _first(
            entry, "cra_rating", "credit_rating", "creditRating", "rating"
        )
        if isinstance(credit_rating, dict):
            # Some payloads may nest the rating as an object.
            credit_rating = _first(
                credit_rating, "rating", "credit_rating", "value", "name"
            )

        records.append(
            BondCentralRawRating(
                isin=isin,
                credit_rating=_clean(credit_rating),
                credit_rating_agency_name=_clean(
                    _first(
                        entry,
                        "credit_rating_agency_name",
                        "credit_rating_agency",
                        "rating_agency_name",
                        "cra_name",
                        "agency",
                    )
                ),
                date_of_credit_rating=_clean(
                    _first(
                        entry,
                        "date_of_credit_rating",
                        "credit_rating_date",
                        "rating_date",
                    )
                ),
                ratings_watch=_clean(_first(entry, "ratings_watch", "rating_watch")),
                ratings_outlook=_clean(
                    _first(entry, "ratings_outlook", "rating_outlook", "outlook")
                ),
                security_status=security_status,
                maturity_date=maturity_date,
                security_name=security_name,
                issuer_name=issuer_name,
            )
        )
    return records



class BondCentralClient:
    """Client for the Bond Central public securities/ratings API."""

    def __init__(self, settings: Settings, timeout: float = 10.0):
        self._settings = settings
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=self._timeout,
                headers=_HEADERS,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_ratings(self, isin: str) -> list[BondCentralRawRating]:
        """Fetch credit-rating rows for a single ISIN.

        Never raises: timeout, HTTP error, empty response and malformed
        payload all yield an empty list.
        """
        isin_norm = (isin or "").strip().upper()
        if not isin_norm:
            return []

        try:
            client = await self._get_client()
            response = await client.get(
                BOND_CENTRAL_SECURITIES_URL,
                params={
                    "isin": isin_norm,
                    "page": _REQUEST_PAGE,
                    "size": _REQUEST_SIZE,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            logger.warning(
                "Bond Central request timed out for %s: %s", isin_norm, exc
            )
            return []
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "error"
            logger.warning("Bond Central HTTP %s for %s", status, isin_norm)
            return []
        except httpx.HTTPError as exc:
            logger.warning(
                "Bond Central request failed for %s: %s", isin_norm, exc
            )
            return []
        except ValueError as exc:
            # response.json() raises (a subclass of) ValueError on bad JSON.
            logger.warning(
                "Bond Central returned an unreadable payload for %s: %s",
                isin_norm,
                exc,
            )
            return []

        if payload is None:
            return []

        records: list[BondCentralRawRating] = []
        for row in _rows(payload):
            records.extend(_extract_rows(_security_payload(row)))
        logger.debug(
            "Bond Central returned %d rating row(s) for %s", len(records), isin_norm
        )
        return records

    async def fetch_securities_page(
        self,
        page: int = 1,
        size: int = _MAX_PAGE_SIZE,
    ) -> tuple[list[BondCentralRawRating], dict[str, Any]]:
        """Retrieve ONE page of the Bond Central securities index.

        Used by the ratings-index synchronization service, which walks the
        pages with the API's own pagination metadata instead of issuing one
        request per ISIN.

        Unlike :meth:`fetch_ratings` this method RAISES on failure so a partial
        sweep can be reported through the index metadata instead of silently
        looking like an empty result:

        * :class:`BondCentralRateLimited` on HTTP 429 (carries ``Retry-After``)
        * :class:`BondCentralFetchError` on timeouts, HTTP errors and
          unreadable/invalid payloads
        """
        page = max(1, int(page))
        size = max(1, min(int(size), _MAX_PAGE_SIZE))

        try:
            client = await self._get_client()
            response = await client.get(
                BOND_CENTRAL_SECURITIES_URL,
                params={"page": page, "size": size},
            )
            if response.status_code == 429:
                raise BondCentralRateLimited(
                    "Bond Central rate limit (HTTP 429)",
                    _retry_after_seconds(response),
                    body_excerpt=_body_excerpt(response),
                )
            response.raise_for_status()
            payload = response.json()
        except BondCentralRateLimited:
            raise
        except httpx.TimeoutException as exc:
            raise BondCentralFetchError(f"timeout after {self._timeout}s: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "error"
            raise BondCentralFetchError(
                f"HTTP {status} for page {page}",
                status_code=status,
                body_excerpt=_body_excerpt(exc.response),
            ) from exc
        except httpx.HTTPError as exc:
            raise BondCentralFetchError(f"request failed: {exc}") from exc
        except ValueError as exc:
            # response.json() raises (a subclass of) ValueError on bad JSON.
            raise BondCentralFetchError(f"unreadable payload: {exc}") from exc

        if payload is None:
            raise BondCentralFetchError("empty response body")

        records: list[BondCentralRawRating] = []
        for row in _rows(payload):
            records.extend(_extract_rows(_security_payload(row)))
        info = _pagination_info(payload)
        logger.debug(
            "Bond Central page %d returned %d rating row(s) (info=%s)",
            page,
            len(records),
            info,
        )
        return records, info
