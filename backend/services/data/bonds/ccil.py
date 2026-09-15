"""CCIL public market-data adapter (NDS-OM / Market Watch).

The current CCIL Market Watch page lives at:
    https://www.ccilindia.com/market-watch

It is backed by a Liferay Portlet
(``com_ccil_ndsom_marketwatch_CcilNDSOMMarketWatchPortlet_INSTANCE_swas``)
and is served by the resource mechanism the page's own JavaScript uses.
Three resource IDs back the three market-watch sections:

    - NDSOMCG     -> Central Government Securities (G-Secs)
    - NDSOMSG     -> State Government Securities (SDLs)
    - NDSOM_TBILL -> Treasury Bills

Each resource returns a JSON wrapper:

    {"result1": "<json-encoded list of records>"}

where ``result1`` itself decodes to a list of record objects. Each record
exposes (among others):

    ismt_idnt  : security description (e.g. "06.94 GS 2036", "182 DTB 18092026")
    mrty_date  : maturity date as DD/MM/YYYY
    ltp        : last-traded value (see FIELD SEMANTICS below)
    lty        : last-traded value (see FIELD SEMANTICS below)
    lta        : last-traded amount
    tta        : total traded amount (Cr.)
    a, b, c, d, e, f : bid/offer auxiliaries (zero-filled / unused in this feed)

FIELD SEMANTICS (verified against the page's own JS and the live payload):
The rendered table has two columns labelled "LTP" (Last Traded Price) and
"LTY" (Last Traded Yield). The JSON field NAMES are swapped relative to
those column headings in the Central/State sections, while the T-Bill
section follows the natural order. Concretely, the page JS emits:

    Central/State : .add([... , lty, ltp, lta, tta])   // into LTP/LTY/LTA/TTA cols
    T-Bills       : .add([... , ltp, lty, lta, tta])   // into LTP/LTY/LTA/TTA cols

So:
    Central/State : JSON ``lty`` = price, JSON ``ltp`` = yield
    T-Bills       : JSON ``ltp`` = price, JSON ``lty`` = yield

This adapter normalizes the JSON fields into semantically-correct
``CcilRawRecord`` fields (``raw.ltp`` = last traded PRICE, ``raw.lty`` =
last traded YIELD) so the Bond normalizer can consume them uniformly. The
zero-filled a-f bid/offer auxiliaries are NOT mapped (their semantics here
are not meaningful / uniformly zero).

NOTE: No ISIN is published in this response. The security description is
preserved verbatim so a future NSE security-master enrichment step can
supply the real ISIN. No ISIN is fabricated.

No paid API, no API key, no commercial data vendor.
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
# CCIL current Market Watch resource mechanism (Portlet-based)
# ---------------------------------------------------------------------------

_CCIL_BASE = "https://www.ccilindia.com"
_MARKET_WATCH_PAGE = f"{_CCIL_BASE}/market-watch"

# Portlet id hard-coded on the current CCIL Market Watch page.
_PORTLET_ID = (
    "com_ccil_ndsom_marketwatch_CcilNDSOMMarketWatchPortlet_INSTANCE_swas"
)


def _resource_url(resource_id: str) -> str:
    """Build a portlet resource URL for a given CCIL market-watch resource id."""
    return (
        f"{_MARKET_WATCH_PAGE}"
        f"?p_p_id={_PORTLET_ID}"
        f"&p_p_lifecycle=2"
        f"&p_p_state=normal"
        f"&p_p_mode=view"
        f"&p_p_resource_id={resource_id}"
        f"&p_p_cacheability=cacheLevelPage"
    )


# Current, publicly accessible CCIL Market Watch endpoints. Discovered from
# the page's own JavaScript (updateTable / ndsomSGUpdateTable /
# ndsomTbillUpdateTable). These are the real production endpoints.
CENTRAL_MARKET_WATCH_URL = _resource_url("NDSOMCG")
STATE_MARKET_WATCH_URL = _resource_url("NDSOMSG")
TBILL_MARKET_WATCH_URL = _resource_url("NDSOM_TBILL")

# CCIL serves the resource to browsers; provide a browser UA.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


class CcilParseError(Exception):
    """Raised when a CCIL Market Watch response cannot be parsed."""


class CcilClient:
    """Client for CCIL public market-watch data.

    Retrieves raw rows and normalizes them into CcilRawRecord objects.
    Parsing is source-specific and stays inside this module.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True, timeout=30.0, headers=_HEADERS
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_central_market_watch(self) -> list[CcilRawRecord]:
        """Fetch Central Government Market Watch rows (resource: NDSOMCG)."""
        return await self._fetch_section("central", CENTRAL_MARKET_WATCH_URL)

    async def fetch_state_market_watch(self) -> list[CcilRawRecord]:
        """Fetch State Government Market Watch rows (resource: NDSOMSG)."""
        return await self._fetch_section("state", STATE_MARKET_WATCH_URL)

    async def fetch_tbill_market_watch(self) -> list[CcilRawRecord]:
        """Fetch T-Bills Market Watch rows (resource: NDSOM_TBILL)."""
        return await self._fetch_section("tbills", TBILL_MARKET_WATCH_URL)

    async def fetch_all(self) -> list[CcilRawRecord]:
        """Fetch all three CCIL sections and return combined raw records.

        Failures of an individual section are logged and isolated; a
        failure in one section does not prevent the others from loading.
        A parsing error raises ``CcilParseError``, which this method
        catches so the rest of the bond layer can continue with the
        remaining sources (see BondService.refresh_all_sources).
        """
        records: list[CcilRawRecord] = []
        for fetch in (
            self.fetch_central_market_watch,
            self.fetch_state_market_watch,
            self.fetch_tbill_market_watch,
        ):
            try:
                rows = await fetch()
                records.extend(rows)
            except CcilParseError as exc:
                logger.warning("CCIL section parse failed (%s): %s", fetch.__name__, exc)
            except Exception as exc:
                logger.warning("CCIL section fetch failed (%s): %s", fetch.__name__, exc)
        return records

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_section(self, section: str, url: str) -> list[CcilRawRecord]:
        """Fetch one CCIL market-watch section and parse it as JSON.

        Raises:
            CcilParseError: if the response is not valid CCIL JSON or the
                expected ``result1`` structure is absent / malformed.
            httpx.HTTPStatusError: on non-2xx HTTP responses.
        """
        logger.info("CCIL fetch section=%s url=%s", section, url)
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return _parse_ccil_json(response.text, section)



# ---------------------------------------------------------------------------
# Parsing helpers (source-specific, internal to this module)
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$")


def _num(text: Any) -> str | None:
    """Return a cleaned numeric string if *text* is numeric, else ``None``.

    Missing / blank / null values become ``None`` (never zero) so the
    normalizer can distinguish genuinely-absent values from zero. Comma
    thousands separators are stripped.
    """
    if text is None:
        return None
    v = str(text).strip()
    if v == "" or v.lower() == "null":
        return None
    v = v.replace(",", "")
    if _NUMERIC_RE.match(v):
        return v
    return None


def _parse_ccil_json(text: str, section: str) -> list[CcilRawRecord]:
    """Parse a CCIL Market Watch JSON wrapper into CcilRawRecord rows.

    The response is a JSON object with a ``result1`` field whose value is
    itself a JSON-encoded list of record objects. This helper:

      1. parses the outer JSON,
      2. validates presence of ``result1``,
      3. JSON-decodes ``result1`` when it is a string,
      4. maps each record into a CcilRawRecord with the section-correct
         price/yield semantics (see module docstring),
      5. skips rows lacking a recognisable security description.

    Raises:
        CcilParseError: if the response cannot be parsed, ``result1`` is
            missing, or ``result1`` is not a list of records.
    """
    # 1. outer JSON
    try:
        wrapper = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise CcilParseError(
            f"CCIL section={section}: outer JSON parse failed: {exc}"
        ) from exc

    if not isinstance(wrapper, dict):
        raise CcilParseError(
            f"CCIL section={section}: expected JSON object, "
            f"got {type(wrapper).__name__}"
        )

    # 2. result1 presence
    if "result1" not in wrapper:
        raise CcilParseError(f"CCIL section={section}: missing 'result1' field")

    # 3. result1 is frequently a JSON-encoded string
    payload = wrapper["result1"]
    if isinstance(payload, str):
        try:
            rows = _json.loads(payload)
        except _json.JSONDecodeError as exc:
            raise CcilParseError(
                f"CCIL section={section}: 'result1' JSON-decode failed: {exc}"
            ) from exc
    else:
        rows = payload

    # 4. validate structure
    if not isinstance(rows, list):
        raise CcilParseError(
            f"CCIL section={section}: 'result1' is "
            f"{type(rows).__name__}, expected list"
        )

    records: list[CcilRawRecord] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        rec = _row_to_record(item, section)
        if rec is not None:
            records.append(rec)

    logger.info("CCIL parsed section=%s rows=%d", section, len(records))
    return records


def _row_to_record(item: dict[str, Any], section: str) -> CcilRawRecord | None:
    """Map one CCIL JSON record object into a CcilRawRecord.

    Section-aware price/yield mapping (see module docstring):
      central/state -> JSON ``lty`` is price, JSON ``ltp`` is yield
      tbills        -> JSON ``ltp`` is price, JSON ``lty`` is yield
    """
    desc = _clean_str(item.get("ismt_idnt"))
    if not desc or len(desc) < 2:
        return None

    mrty = _clean_str(item.get("mrty_date")) or None

    if section in ("central", "state"):
        price = _num(item.get("lty"))   # JSON lty -> last traded price
        yield_ = _num(item.get("ltp"))  # JSON ltp -> last traded yield
    else:  # tbills
        price = _num(item.get("ltp"))   # JSON ltp -> last traded price
        yield_ = _num(item.get("lty"))  # JSON lty -> last traded yield

    return CcilRawRecord(
        section=section,
        security_description=desc,
        security_name=desc,
        maturity_date=mrty,
        ltp=price,
        lty=yield_,
        lta=_num(item.get("lta")),
        tta=_num(item.get("tta")),
        # bid/offer auxiliaries (a-f) are zero-filled / unused in this feed.
        isin=None,
        coupon_rate=None,
    )


def _clean_str(text: Any) -> str:
    """Trim/squash whitespace from a string field (None-safe)."""
    if text is None:
        return ""
    return str(text).strip()
