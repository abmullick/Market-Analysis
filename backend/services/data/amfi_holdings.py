"""Isolated AMFI Scheme Wise Disclosure holdings retrieval layer.

Used by the future Portfolio Builder "Stock Overlap & Concentration" feature.

Source (established by prior investigation, Next.js chunk
``app/otherdata/scheme-wise-disclosure/page-*.js``)::

    GET https://www.amfiindia.com/api/schemewisedisclosure-investment
        ?MF_ID=<AMFI AMC id>&strMonth=<DD-Mon-YYYY quarter start>[&excel=true]

The API is AMC x quarter, NOT scheme x quarter, so callers must group
selected schemes by AMC and fetch each AMC/quarter only once.

Isolated: does NOT touch ``data/amfi.py`` (NAVAll), ``fetcher.py``,
portfolio analysis, what-if logic, endpoints, or existing models.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import httpx

from backend.utils.logging import logger

AMFI_SCHEME_WISE_BASE_URL = (
    "https://www.amfiindia.com/api/schemewisedisclosure-investment"
)

#: Latest quarter start verified live (MF_ID=18 returned 80 rows).
#: Historical quarter selection is out of scope for now.
DEFAULT_STR_MONTH = "01-Apr-2026"

# --- AMC -> MF_ID (explicit, hand-maintained) ---
# Keys are normalized via normalize_amc_name(); values are AMFI mf_id
# strings embedded in the Scheme Wise Disclosure page. Unknown AMCs
# resolve to None (reported unmatched) -- never guessed.
AMC_TO_MF_ID: dict[str, str] = {
    "360 one mutual fund": "62",
    "aditya birla sun life mutual fund": "3",
    "axis mutual fund": "53",
    "bandhan mutual fund": "48",
    "bank of india mutual fund": "46",
    "baroda bnp paribas mutual fund": "4",
    "canara robeco mutual fund": "32",
    "dsp mutual fund": "6",
    "edelweiss mutual fund": "47",
    "franklin templeton mutual fund": "27",
    "groww mutual fund": "63",
    "hdfc mutual fund": "9",
    "hsbc mutual fund": "37",
    "icici prudential mutual fund": "20",
    "invesco mutual fund": "42",
    "iti mutual fund": "70",
    "jm financial mutual fund": "16",
    "kotak mahindra mutual fund": "17",
    "lic mutual fund": "18",
    "mirae asset mutual fund": "45",
    "motilal oswal mutual fund": "21",
    "nippon india mutual fund": "30",
    "parag parikh mutual fund": "73",
    "pgim india mutual fund": "74",
    "quant mutual fund": "33",
    "sbi mutual fund": "25",
    "sundaram mutual fund": "26",
    "tata mutual fund": "28",
    "taurus mutual fund": "83",
    "uti mutual fund": "71",
    "zerodha mutual fund": "77",
}
def normalize_amc_name(amc: str | None) -> str:
    """Normalize AMC name for AMC_TO_MF_ID lookup (lookup only)."""
    if not amc:
        return ""
    text = unicodedata.normalize("NFKD", amc)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_mf_id(amc: str | None) -> str | None:
    """Return AMFI MF_ID for an application AMC name, if known."""
    return AMC_TO_MF_ID.get(normalize_amc_name(amc))


_AND_RE = re.compile(r"\s+and\s+", re.IGNORECASE)


def normalize_scheme_name(name: str | None) -> str:
    """Strict scheme-name normalization.

    Only superficial differences: case, repeated whitespace,
    punctuation, ``&`` vs ``and``. Meaningful terms (Direct/Regular,
    Growth/IDCW/Dividend, Plan/Option, ...) are preserved.
    """
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("&", " and ")
    text = _AND_RE.sub(" and ", f" {text} ").strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_amfi_scheme(
    scheme_name: str,
    amfi_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Match app scheme name to a UNIQUE AMFI (Scheme_ID, Scheme_Name).

    Returns (key, scheme_id, scheme_name) or (None, None, None) when
    zero or more than one distinct AMFI scheme matches -- caller then
    reports the scheme as unmatched instead of guessing.
    """
    target = normalize_scheme_name(scheme_name)
    if not target:
        return None, None, None
    candidates: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in amfi_rows:
        if normalize_scheme_name(str(row.get("Scheme_Name") or "")) == target:
            key = (str(row.get("Scheme_ID") or ""),
                   str(row.get("Scheme_Name") or ""))
            candidates.setdefault(key, []).append(row)
    if len(candidates) != 1:
        return None, None, None
    (sid, label), _rows = next(iter(candidates.items()))
    return {"amfi_scheme_id": sid, "amfi_scheme_name": label}, sid, label
EQUITY_MARKERS = ("equit",)
NON_EQUITY_MARKERS = (
    "future", "option", "swap", "forward", "treps", "tri-party",
    "reverse repo", "repo", "cash", "call money",
    "certificate of deposit", "commercial paper",
    "treasury bill", "t-bill", "government securit", "g-sec", "gsec",
    "corporate bond", "debenture", " ncd", "ncd ",
    "non convertible", "non-convertible", "bond",
    "securitised", "securitized", "pass through", "pass-through",
    "ptc ", "interest rate", "currency", "commodity",
)


def is_equity_security(security_type: str | None) -> bool:
    """True only for underlying equity (uses Security_Type exclusively)."""
    text = (security_type or "").lower()
    if not text:
        return False
    if any(m in text for m in NON_EQUITY_MARKERS):
        return False
    return any(m in text for m in EQUITY_MARKERS)


@dataclass
class AmfiHolding:
    """Normalized internal holding (no quantity: AMFI omits it)."""

    scheme_code: str
    scheme_name: str
    amfi_scheme_id: str
    amfi_scheme_name: str
    isin: str
    security_name: str
    security_type: str
    market_value: float | None
    portfolio_weight: float | None


@dataclass
class AmfiHoldingsResult:
    holdings: list[AmfiHolding] = field(default_factory=list)
    unmatched: list[dict[str, Any]] = field(default_factory=list)
    quarter: str = DEFAULT_STR_MONTH


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_holding_row(
    row: Mapping[str, Any],
    *,
    scheme_code: str,
    scheme_name: str,
    amfi_scheme_id: str,
    amfi_scheme_name: str,
) -> AmfiHolding:
    """Map raw AMFI JSON row -> AmfiHolding."""
    return AmfiHolding(
        scheme_code=str(scheme_code),
        scheme_name=str(scheme_name),
        amfi_scheme_id=str(amfi_scheme_id or ""),
        amfi_scheme_name=str(amfi_scheme_name or row.get("Scheme_Name") or ""),
        isin=str(row.get("ISIN") or "").strip(),
        security_name=str(row.get("Company_Name") or "").strip(),
        security_type=str(row.get("Security_Type") or "").strip(),
        market_value=_safe_float(row.get("MarketValue")),
        portfolio_weight=_safe_float(row.get("MarketValuePercentage")),
    )


class AmfiHoldingsError(Exception):
    """AMFI scheme-wise request failure."""
class AmfiHoldingsService:
    """Group selections by MF_ID; fetch each AMC x quarter once."""

    def __init__(
        self,
        base_url: str = AMFI_SCHEME_WISE_BASE_URL,
        str_month: str = DEFAULT_STR_MONTH,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.str_month = str_month
        self.timeout = timeout
        self._raw_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    @staticmethod
    def _parts(sel: Any) -> tuple[str, str, Any]:
        if isinstance(sel, Mapping):
            return (str(sel.get("scheme_code") or ""),
                    str(sel.get("scheme_name") or ""), sel.get("amc"))
        return (str(getattr(sel, "scheme_code", "") or ""),
                str(getattr(sel, "scheme_name", "") or ""),
                getattr(sel, "amc", None))

    async def fetch_amc_rows(
        self,
        mf_id: str,
        str_month: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> list[dict[str, Any]]:
        """GET raw JSON rows for one AMC x quarter (in-process cached)."""
        month = str_month or self.str_month
        key = (str(mf_id), month)
        if key in self._raw_cache:
            logger.debug("AMFI holdings cache hit: %s", key)
            return self._raw_cache[key]
        params = {"MF_ID": str(mf_id), "strMonth": month}
        logger.info("Fetching AMFI scheme-wise disclosure: %s", params)
        try:
            if client is not None:
                resp = await client.get(
                    self.base_url, params=params, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(
                        follow_redirects=True) as hc:
                    resp = await hc.get(
                        self.base_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            raise AmfiHoldingsError(
                f"AMFI request failed MF_ID={mf_id} "
                f"strMonth={month}: {exc}") from exc
        rows: list[dict[str, Any]] = []
        if isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)]
        elif not isinstance(payload, dict):
            raise AmfiHoldingsError(
                f"Unexpected AMFI payload: {type(payload).__name__}")
        # dict payload == {"message": "Nil"/"No data found."} -> empty
        self._raw_cache[key] = rows
        return rows

    async def fetch_holdings(
        self,
        selections: Sequence[Any],
        str_month: str | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        equity_only: bool = True,
    ) -> AmfiHoldingsResult:
        """Fetch + normalize holdings (one HTTP call per AMC)."""
        month = str_month or self.str_month
        result = AmfiHoldingsResult(quarter=month)
        groups: dict[str, list[tuple[str, str]]] = {}
        for sel in selections:
            code, name, amc = self._parts(sel)
            mf_id = resolve_mf_id(amc)
            if not mf_id or not code or not name:
                result.unmatched.append({
                    "scheme_code": code, "scheme_name": name, "amc": amc,
                    "reason": ("unknown_amc" if not mf_id
                               else "missing_scheme_identity")})
                continue
            groups.setdefault(mf_id, []).append((code, name))
        for mf_id, members in groups.items():
            try:
                rows = await self.fetch_amc_rows(mf_id, month, client=client)
            except AmfiHoldingsError as exc:
                logger.warning("AMFI holdings fetch failed: %s", exc)
                for code, name in members:
                    result.unmatched.append({
                        "scheme_code": code, "scheme_name": name,
                        "mf_id": mf_id, "reason": "fetch_failed"})
                continue
            for code, name in members:
                matched, sid, label = match_amfi_scheme(name, rows)
                if matched is None:
                    result.unmatched.append({
                        "scheme_code": code, "scheme_name": name,
                        "mf_id": mf_id,
                        "reason": "no_unique_amfi_scheme_match"})
                    continue
                want = normalize_scheme_name(label or "")
                for row in rows:
                    sname = normalize_scheme_name(
                        str(row.get("Scheme_Name") or ""))
                    if sname != want:
                        continue
                    stype = row.get("Security_Type")
                    if equity_only and not is_equity_security(stype):
                        continue
                    result.holdings.append(normalize_holding_row(
                        row, scheme_code=code, scheme_name=name,
                        amfi_scheme_id=sid or "",
                        amfi_scheme_name=label or ""))
        return result
