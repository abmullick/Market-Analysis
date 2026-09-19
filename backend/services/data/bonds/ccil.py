
"""CCIL public market-data adapter (NDS-OM / Market Watch).

The current CCIL Market Watch page lives at:
    https://www.ccilindia.com/market-watch

The adapter uses the Liferay portlet resource mechanism used by the
CCIL Market Watch page.

Resource IDs:
    NDSOMCG       -> Central Government Securities
    NDSOMSG       -> State Government Securities
    NDSOM_TBILL   -> Treasury Bills

The adapter preserves the existing parsing and field-mapping logic while
adding session priming and detailed diagnostics for troubleshooting.
"""

from __future__ import annotations

import json as _json
import re
from typing import Any

import httpx

from backend.config.settings import Settings
from backend.models.bonds import CcilRawRecord
from backend.utils.logging import logger


# ---------------------------------------------------------------------------
# CCIL Market Watch configuration
# ---------------------------------------------------------------------------

_CCIL_BASE = "https://www.ccilindia.com"
_MARKET_WATCH_PAGE = f"{_CCIL_BASE}/market-watch"

_PORTLET_ID = (
    "com_ccil_ndsom_marketwatch_CcilNDSOMMarketWatchPortlet_INSTANCE_swas"
)


def _resource_url(resource_id: str) -> str:
    """Build a CCIL Liferay resource URL."""
    return (
        f"{_MARKET_WATCH_PAGE}"
        f"?p_p_id={_PORTLET_ID}"
        f"&p_p_lifecycle=2"
        f"&p_p_state=normal"
        f"&p_p_mode=view"
        f"&p_p_resource_id={resource_id}"
        f"&p_p_cacheability=cacheLevelPage"
    )


CENTRAL_MARKET_WATCH_URL = _resource_url("NDSOMCG")
STATE_MARKET_WATCH_URL = _resource_url("NDSOMSG")
TBILL_MARKET_WATCH_URL = _resource_url("NDSOM_TBILL")


# ---------------------------------------------------------------------------
# HTTP headers
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept": (
        "application/json, text/javascript, */*; q=0.01"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": _MARKET_WATCH_PAGE,
    "Connection": "keep-alive",
}

_RESOURCE_HEADERS = {
    **_HEADERS,
    "X-Requested-With": "XMLHttpRequest",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CcilParseError(Exception):
    """Raised when a CCIL Market Watch response cannot be parsed."""


# ---------------------------------------------------------------------------
# CCIL client
# ---------------------------------------------------------------------------


class CcilClient:
    """Client for CCIL public Market Watch data."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: httpx.AsyncClient | None = None
        self._session_primed = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Create or return a reusable HTTP session."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers=_HEADERS,
            )
            self._session_primed = False

        return self._client

    async def _prime_session(self) -> None:
        """Load the main Market Watch page before resource requests.

        This preserves cookies/session state and makes the request sequence
        closer to how a browser loads the CCIL page.
        """
        if self._session_primed:
            return

        client = await self._get_client()

        logger.info(
            "CCIL session prime started url=%s",
            _MARKET_WATCH_PAGE,
        )

        response = await client.get(
            _MARKET_WATCH_PAGE,
            headers=_HEADERS,
        )

        logger.info(
            (
                "CCIL session prime response "
                "status=%s content_type=%s body_length=%d "
                "final_url=%s"
            ),
            response.status_code,
            response.headers.get("content-type"),
            len(response.text),
            str(response.url),
        )

        response.raise_for_status()
        self._session_primed = True

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

        self._client = None
        self._session_primed = False

    async def fetch_central_market_watch(
        self,
    ) -> list[CcilRawRecord]:
        """Fetch Central Government Market Watch rows."""
        return await self._fetch_section(
            "central",
            CENTRAL_MARKET_WATCH_URL,
        )

    async def fetch_state_market_watch(
        self,
    ) -> list[CcilRawRecord]:
        """Fetch State Government Market Watch rows."""
        return await self._fetch_section(
            "state",
            STATE_MARKET_WATCH_URL,
        )

    async def fetch_tbill_market_watch(
        self,
    ) -> list[CcilRawRecord]:
        """Fetch Treasury Bills Market Watch rows."""
        return await self._fetch_section(
            "tbills",
            TBILL_MARKET_WATCH_URL,
        )

    async def fetch_all(self) -> list[CcilRawRecord]:
        """Fetch all three CCIL Market Watch sections.

        Errors in one section are isolated so the remaining sections
        can still be attempted.
        """
        records: list[CcilRawRecord] = []

        try:
            await self._prime_session()
        except Exception as exc:
            logger.warning(
                "CCIL session priming failed: %s",
                exc,
            )

        for fetch in (
            self.fetch_central_market_watch,
            self.fetch_state_market_watch,
            self.fetch_tbill_market_watch,
        ):
            try:
                rows = await fetch()
                records.extend(rows)

            except CcilParseError as exc:
                logger.warning(
                    "CCIL section parse failed (%s): %s",
                    fetch.__name__,
                    exc,
                )

            except Exception as exc:
                logger.warning(
                    "CCIL section fetch failed (%s): %s",
                    fetch.__name__,
                    exc,
                )

        logger.info(
            "CCIL total records fetched=%d",
            len(records),
        )

        return records

    # ------------------------------------------------------------------
    # Internal HTTP and parsing helpers
    # ------------------------------------------------------------------

    async def _fetch_section(
        self,
        section: str,
        url: str,
    ) -> list[CcilRawRecord]:
        """Fetch and parse one CCIL Market Watch section."""

        logger.info(
            "CCIL fetch started section=%s url=%s",
            section,
            url,
        )

        client = await self._get_client()

        response = await client.get(
            url,
            headers=_RESOURCE_HEADERS,
        )

        response_text = response.text
        content_type = response.headers.get("content-type")

        logger.info(
            (
                "CCIL response diagnostics "
                "section=%s status=%s content_type=%s "
                "body_length=%d final_url=%s"
            ),
            section,
            response.status_code,
            content_type,
            len(response_text),
            str(response.url),
        )

        logger.info(
            "CCIL response preview section=%s body_prefix=%r",
            section,
            response_text[:300],
        )

        if response.status_code != 200:
            logger.warning(
                (
                    "CCIL non-success response "
                    "section=%s status=%s headers=%s"
                ),
                section,
                response.status_code,
                dict(response.headers),
            )

        response.raise_for_status()

        return _parse_ccil_json(
            response_text,
            section,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(
    r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$"
)


def _num(text: Any) -> str | None:
    """Return a cleaned numeric string if text is numeric.

    Missing, blank, and null values become None.
    Comma thousands separators are removed.
    """
    if text is None:
        return None

    value = str(text).strip()

    if value == "" or value.lower() == "null":
        return None

    value = value.replace(",", "")

    if _NUMERIC_RE.match(value):
        return value

    return None


def _parse_ccil_json(
    text: str,
    section: str,
) -> list[CcilRawRecord]:
    """Parse a CCIL JSON response.

    Expected structure:

        {
            "result1": "<json-encoded list>"
        }
    """

    # ---------------------------------------------------------------
    # 1. Parse outer JSON
    # ---------------------------------------------------------------

    try:
        wrapper = _json.loads(text)

    except _json.JSONDecodeError as exc:
        raise CcilParseError(
            f"CCIL section={section}: "
            f"outer JSON parse failed: {exc}"
        ) from exc

    if not isinstance(wrapper, dict):
        raise CcilParseError(
            f"CCIL section={section}: expected JSON object, "
            f"got {type(wrapper).__name__}"
        )

    # ---------------------------------------------------------------
    # 2. Validate result1
    # ---------------------------------------------------------------

    if "result1" not in wrapper:
        raise CcilParseError(
            f"CCIL section={section}: "
            "missing 'result1' field"
        )

    payload = wrapper["result1"]

    # ---------------------------------------------------------------
    # 3. Decode result1 when it is a JSON string
    # ---------------------------------------------------------------

    if isinstance(payload, str):
        try:
            rows = _json.loads(payload)

        except _json.JSONDecodeError as exc:
            raise CcilParseError(
                f"CCIL section={section}: "
                f"'result1' JSON decode failed: {exc}"
            ) from exc

    else:
        rows = payload

    # ---------------------------------------------------------------
    # 4. Validate list structure
    # ---------------------------------------------------------------

    if not isinstance(rows, list):
        raise CcilParseError(
            f"CCIL section={section}: "
            f"'result1' is {type(rows).__name__}, "
            "expected list"
        )

    # ---------------------------------------------------------------
    # 5. Convert rows
    # ---------------------------------------------------------------

    records: list[CcilRawRecord] = []

    for item in rows:
        if not isinstance(item, dict):
            logger.warning(
                "CCIL section=%s skipping non-dict row: %r",
                section,
                item,
            )
            continue

        record = _row_to_record(
            item,
            section,
        )

        if record is not None:
            records.append(record)

    logger.info(
        "CCIL parsed section=%s rows=%d",
        section,
        len(records),
    )

    return records


def _row_to_record(
    item: dict[str, Any],
    section: str,
) -> CcilRawRecord | None:
    """Convert one CCIL JSON row into CcilRawRecord.

    Central/State:
        JSON lty -> price
        JSON ltp -> yield

    T-Bills:
        JSON ltp -> price
        JSON lty -> yield
    """

    description = _clean_str(
        item.get("ismt_idnt")
    )

    if not description or len(description) < 2:
        logger.debug(
            "CCIL section=%s skipping row without description: %r",
            section,
            item,
        )
        return None

    maturity_date = (
        _clean_str(item.get("mrty_date"))
        or None
    )

    if section in ("central", "state"):
        price = _num(
            item.get("lty")
        )

        yield_ = _num(
            item.get("ltp")
        )

    else:
        price = _num(
            item.get("ltp")
        )

        yield_ = _num(
            item.get("lty")
        )

    return CcilRawRecord(
        section=section,
        security_description=description,
        security_name=description,
        maturity_date=maturity_date,
        ltp=price,
        lty=yield_,
        lta=_num(item.get("lta")),
        tta=_num(item.get("tta")),
        isin=None,
        coupon_rate=None,
    )


def _clean_str(text: Any) -> str:
    """Trim whitespace from a string field."""
    if text is None:
        return ""

    return str(text).strip()