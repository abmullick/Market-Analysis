"""Bank of India Mutual Fund (BOI MF) monthly-portfolio fallback adapter.

Fallback for the Stock Overlap feature when the central AMFI scheme-wise
disclosure source returns no holdings for Bank of India Mutual Fund
(AMFI ``MF_ID=46``).

Official BOI sources (confirmed):
- Investor Corner: https://www.boimf.in/investor-corner
- Document API: POST https://www.boimf.in/AjaxService.asmx/GetDocuments
  with ``{"pagno": 0, "category": null, "fromDate": null, "toDate": null,
  "LibraryName": "InvestorCorner", "folderName": "MONTHLY PORTFOLIO",
  "CategoryValue": "no"}``. The response holds a ``Documents`` list whose
  entries provide the official monthly-portfolio XLSX URL.

The workbook has an ``Index`` sheet mapping BOI workbook sheet IDs (e.g.
``YB04`` -- an example only, never hardcoded) to scheme names, and one
worksheet per scheme with a column header row like::

    Name of the Instrument | ISIN | Industry / Rating | Quantity |
    Market/Fair Value (Rs. in Lacs) | % to Net Assets | YTM

Only listed equity/equity-related rows are extracted; T-bills, CDs,
TREPS/reverse repo, cash, receivables/payables, debt, derivatives and
summary rows are excluded. ISIN is the primary security identifier.

Holdings are returned as :class:`AmfiHolding` (same schema as
``AmfiHoldingsService``) so ``stock_overlap.py`` consumes them unchanged.

XLSX parsing uses only the stdlib (``zipfile`` + ``xml``) so no new
dependency is introduced (``openpyxl`` is not in requirements).
"""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree as ET

import httpx

from backend.services.data.amfi_holdings import (
    AmfiHolding,
    AmfiHoldingsResult,
    normalize_amc_name,
    normalize_scheme_name,
)
from backend.utils.logging import logger

BOI_DOCUMENT_API_URL = "https://www.boimf.in/AjaxService.asmx/GetDocuments"
BOI_SITE_BASE = "https://www.boimf.in"

#: AMFI MF_ID for Bank of India Mutual Fund (central source key).
BOI_MF_ID = "46"

BOI_DOCUMENT_PAYLOAD: dict[str, Any] = {
    "pagno": 0,
    "category": None,
    "fromDate": None,
    "toDate": None,
    "LibraryName": "InvestorCorner",
    "folderName": "MONTHLY PORTFOLIO",
    "CategoryValue": "no",
}

#: Equity security_type label attached to BOI rows (no quantity invented).
BOI_EQUITY_SECURITY_TYPE = "Equity & Equity related - Listed"


class BoiHoldingsError(Exception):
    """BOI fallback acquisition/parsing failure."""


def is_boi_selection(amc: str | None) -> bool:
    """True when the selection belongs to Bank of India Mutual Fund."""
    return normalize_amc_name(amc) == "bank of india mutual fund"


_PARENS_RE = re.compile(r"\s*\([^()]*\)")


def strip_parenthetical(text: str | None) -> str:
    """Remove descriptive ``( ... )`` segments from a BOI scheme name."""
    if not text:
        return ""
    cleaned = _PARENS_RE.sub("", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def boi_short_name(name: str | None) -> str:
    """Normalized BOI scheme name with parenthetical descriptors removed."""
    return normalize_scheme_name(strip_parenthetical(name))


ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


def normalize_isin(value: Any) -> str:
    """Uppercase, space-free ISIN or ``""`` when not a valid ISIN."""
    if value is None:
        return ""
    text = re.sub(r"\s+", "", str(value)).upper()
    return text if ISIN_RE.match(text) else ""


#: Markers (lowercased) identifying non-equity BOI rows by instrument name.
BOI_NON_EQUITY_NAME_MARKERS = (
    "treasury bill",
    "t-bill",
    "91 dtb",
    "91dtb",
    "treps",
    "tri-party",
    "triparty",
    "reverse repo",
    "certificate of deposit",
    "commercial paper",
    "fixed deposit",
    "collateral",
    "cash",
    "receivable",
    "payable",
    "ncd",
    "non-convertible",
    "non convertible",
    "debenture",
    " bond",
    "bond ",
    "future",
    "option",
    "swap",
    "forward",
    "derivative",
    "f&o",
    "f & o",
    "hedg",
    "total",
    "subtotal",
    "grand",
)


def is_boi_non_equity_name(name: str | None) -> bool:
    """True when the instrument name is a non-equity/summary row."""
    text = (name or "").strip().lower()
    if not text:
        return True
    return any(m in text for m in BOI_NON_EQUITY_NAME_MARKERS)
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    ctype = cell.get("t")
    value_el = None
    for child in cell:
        if _local(child.tag) == "v":
            value_el = child
            break
    if value_el is None or value_el.text is None:
        inline = []
        for child in cell:
            if _local(child.tag) == "is":
                for node in child.iter():
                    if _local(node.tag) == "t" and node.text:
                        inline.append(node.text)
        return "".join(inline).strip()
    raw = value_el.text.strip()
    if ctype == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return ""
    return raw


def read_xlsx_sheets(data: bytes) -> dict[str, list[list[str]]]:
    """Read XLSX into {sheet_name: rows of text} (stdlib only).

    Each ``<sheet>`` in ``xl/workbook.xml`` carries an ``r:id`` that must
    be resolved through ``xl/_rels/workbook.xml.rels``
    (``Id -> Target``). List order in the .rels file is NOT guaranteed to
    match workbook sheet order, so positional mapping is invalid.
    """
    archive = zipfile.ZipFile(BytesIO(data))
    shared: list[str] = []
    try:
        sst_raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        sst_raw = b""
    if sst_raw:
        for si in ET.fromstring(sst_raw).iter():
            if _local(si.tag) == "si":
                shared.append("".join(
                    t.text for t in si.iter()
                    if _local(t.tag) == "t" and t.text) or "")
    try:
        wb_raw = archive.read("xl/workbook.xml")
    except KeyError as exc:
        raise BoiHoldingsError("XLSX missing xl/workbook.xml") from exc
    names: list[str] = []
    rids: list[str] = []
    for el in ET.fromstring(wb_raw).iter():
        if _local(el.tag) == "sheet":
            names.append(el.get("name") or "")
            rid = None
            for attr, value in el.attrib.items():
                if _local(attr) == "id":
                    rid = value
                    break
            rids.append(rid or "")
    rel_targets: dict[str, str] = {}
    try:
        rels_raw = archive.read("xl/_rels/workbook.xml.rels")
    except KeyError:
        rels_raw = b""
    if rels_raw:
        for el in ET.fromstring(rels_raw).iter():
            if _local(el.tag) == "Relationship":
                rel_id = el.get("Id") or ""
                target = el.get("Target") or ""
                if rel_id and target:
                    rel_targets[rel_id] = target
    sheets: dict[str, list[list[str]]] = {}
    for idx, name in enumerate(names):
        rid = rids[idx] if idx < len(rids) else ""
        target = rel_targets.get(rid, "")
        if target:
            # Targets are relative to xl/ (e.g. "worksheets/sheet1.xml",
            # "../worksheets/sheet1.xml", or absolute "/xl/worksheets/...").
            cleaned = target.strip().lstrip("/")
            while cleaned.startswith("../"):
                cleaned = cleaned[3:]
            if cleaned.startswith("xl/"):
                path = cleaned
            else:
                path = "xl/" + cleaned.lstrip("/")
        else:
            path = f"xl/worksheets/sheet{idx + 1}.xml"
        try:
            sheet_raw = archive.read(path)
        except KeyError:
            sheets[name] = []
            continue
        rows: list[list[str]] = []
        for row_el in ET.fromstring(sheet_raw).iter():
            if _local(row_el.tag) != "row":
                continue
            rows.append([_cell_text(c, shared)
                         for c in row_el if _local(c.tag) == "c"])
        sheets[name] = rows
    return sheets
def _norm_header(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


HEADER_ALIASES = {
    "name": ("name of the instrument", "name of instrument", "instrument",
             "security name", "company name", "scrip name", "particulars"),
    "isin": ("isin",),
    "market_value": ("market fair value rs in lacs", "market fair value",
                     "market value", "fair value", "value rs in lacs"),
    "weight": ("to net assets", "net assets",
               "portfolio weight", "weight", "holding"),
}


def find_header_row(
        rows: Sequence[Sequence[str]]) -> tuple[int, dict[str, int]]:
    """Locate holdings header by column names (no fixed row numbers)."""
    for idx, row in enumerate(rows):
        normed = [_norm_header(c) for c in row]
        mapping: dict[str, int] = {}
        for field, aliases in HEADER_ALIASES.items():
            for col, cell in enumerate(normed):
                if any(a in cell for a in aliases):
                    mapping[field] = col
                    break
        if all(k in mapping for k in ("name", "isin", "weight")):
            return idx, mapping
    raise BoiHoldingsError("Holdings header row not found in scheme sheet")


def parse_index_sheet(rows: Sequence[Sequence[str]]) -> dict[str, str]:
    """Parse Index sheet -> {SHEET_ID: full scheme name} (fresh per file)."""
    mapping: dict[str, str] = {}
    for row in rows:
        cells = [str(c or "").strip() for c in row]
        if len(cells) < 2 or not cells[0] or not cells[1]:
            continue
        if re.fullmatch(r"[A-Za-z]{1,4}\d{1,4}", cells[0]):
            mapping[cells[0].upper()] = cells[1]
    return mapping


def resolve_boi_sheet_id(
    requested_scheme_name: str,
    index_mapping: Mapping[str, str],
) -> tuple[str, str]:
    """Resolve workbook sheet ID for the AMFI scheme name (unique match)."""
    target = boi_short_name(requested_scheme_name)
    if not target:
        raise BoiHoldingsError("Empty requested scheme name")
    matches = [(sid, label) for sid, label in index_mapping.items()
               if boi_short_name(label) == target]
    if not matches:
        remainder = target.replace("bank of india", "").strip()
        if remainder:
            cand = [(sid, label) for sid, label in index_mapping.items()
                    if boi_short_name(label) in (target, remainder)
                    or boi_short_name(label).endswith(remainder)]
            matches = cand
    unique = {(sid, boi_short_name(label)) for sid, label in matches}
    if len(unique) != 1:
        raise BoiHoldingsError(
            f"BOI scheme not uniquely resolvable: {requested_scheme_name!r}")
    return matches[0][0], matches[0][1]
def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "--", "NA", "N/A", "NIL", "Nil"}:
        return None
    pct = text.endswith("%")
    if pct:
        text = text[:-1].strip()
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number


_EQUITY_SECTION_MARKERS = (
    "equity & equity related",
    "equity and equity related",
    "listed / awaiting listing",
    "listed/awaiting listing",
    "awaiting listing",
)


def parse_scheme_sheet_holdings(
    rows: Sequence[Sequence[str]],
    *,
    scheme_code: str,
    scheme_name: str,
    amfi_scheme_name: str | None = None,
) -> list[AmfiHolding]:
    """Extract listed-equity holdings from one scheme worksheet."""
    _hidx, cols = find_header_row(rows)
    name_c = cols["name"]
    isin_c = cols["isin"]
    weight_c = cols["weight"]
    mv_c = cols.get("market_value")

    def cell(row: Sequence[str], idx: int) -> str:
        return str(row[idx]).strip() if idx < len(row) else ""

    holdings: list[AmfiHolding] = []
    in_equity = False
    seen_equity_header = False
    for row in rows[_hidx + 1:]:
        first = cell(row, 0).lower()
        name = cell(row, name_c)
        lname = name.lower()
        # Section tracking: equity section opens at the equity header,
        # closes at the first subsequent money-market/debt/cash/summary
        # section header. Header-row repeats are skipped.
        if ("equity" in first or "equity" in lname) and (
                "related" in first or "related" in lname):
            in_equity = True
            seen_equity_header = True
            continue
        if _norm_header(name) == _norm_header(cell(row, name_c)) and (
                "name of the instrument" in lname):
            continue
        isin = normalize_isin(cell(row, isin_c))
        if seen_equity_header and not in_equity:
            continue
        if not seen_equity_header:
            # No explicit section headers: accept ISIN rows until a
            # non-equity section header appears.
            if any(m in lname or m in first for m in (
                    "money market", "treasury", "treps", "reverse repo",
                    "receivable", "payable", "derivative", "future",
                    "option", "debt instrument", "certificate of deposit",
                    "commercial paper", "total", "net assets", " nav")):
                break
        else:
            if any(m in lname or m in first for m in (
                    "money market", "treasury", "treps", "reverse repo",
                    "receivable", "payable", "derivative", "future",
                    "option", "debt instrument", "certificate of deposit",
                    "commercial paper", " net total", "total", "net assets",
                    " nav")) and not isin:
                in_equity = False
                continue
            if not in_equity:
                continue
        if not isin or is_boi_non_equity_name(name):
            continue
        weight = _safe_float(cell(row, weight_c))
        if weight is None:
            continue
        mv = _safe_float(cell(row, mv_c)) if mv_c is not None else None
        holdings.append(AmfiHolding(
            scheme_code=str(scheme_code),
            scheme_name=str(scheme_name),
            amfi_scheme_id="",
            amfi_scheme_name=str(amfi_scheme_name or scheme_name),
            isin=isin,
            security_name=name,
            security_type=BOI_EQUITY_SECURITY_TYPE,
            market_value=mv,
            portfolio_weight=weight,
        ))
    return holdings
def extract_document_url(payload: Any) -> str:
    """Return latest monthly-portfolio XLSX URL from GetDocuments."""
    docs: Any = None
    if isinstance(payload, Mapping):
        inner = payload.get("d")
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except (TypeError, ValueError):
                inner = None
        if isinstance(inner, Mapping):
            docs = inner.get("Documents")
        elif isinstance(inner, list):
            docs = inner
        if docs is None:
            for key in ("Documents", "documents", "Data", "data"):
                if isinstance(payload.get(key), list):
                    docs = payload[key]
                    break
    if not isinstance(docs, list) or not docs:
        raise BoiHoldingsError("No BOI monthly-portfolio documents found")
    for doc in docs:
        if not isinstance(doc, Mapping):
            continue
        for key in ("DocumentUrl", "Url", "FileUrl", "Path", "Link"):
            url = str(doc.get(key) or "").strip()
            if url.lower().endswith(".xlsx"):
                if url.startswith("http"):
                    return url
                return BOI_SITE_BASE + url
    for doc in docs:
        if not isinstance(doc, Mapping):
            continue
        for value in doc.values():
            if isinstance(value, str) and "xlsx" in value.lower():
                url = value.strip()
                if url.startswith("http"):
                    return url
                return BOI_SITE_BASE + url
    raise BoiHoldingsError("No XLSX URL in BOI documents response")
class BoiHoldingsAdapter:
    """AMC fallback adapter: BOI implementation.

    Future AMC adapters implement ``fetch_holdings(selections)`` returning
    ``AmfiHoldingsResult`` with ``AmfiHolding`` rows. One workbook download
    is shared across all selected BOI schemes (in-process URL cache).
    """

    document_url = BOI_DOCUMENT_API_URL
    document_payload: dict[str, Any] = dict(BOI_DOCUMENT_PAYLOAD)

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._workbook_cache: dict[str, bytes] = {}

    @staticmethod
    def _parts(sel: Any) -> tuple[str, str, Any]:
        if isinstance(sel, Mapping):
            return (str(sel.get("scheme_code") or ""),
                    str(sel.get("scheme_name") or ""), sel.get("amc"))
        return (str(getattr(sel, "scheme_code", "") or ""),
                str(getattr(sel, "scheme_name", "") or ""),
                getattr(sel, "amc", None))

    async def discover_xlsx_url(
        self, client: httpx.AsyncClient | None = None,
    ) -> str:
        """POST the BOI document API, return latest XLSX URL."""
        logger.info("Discovering BOI monthly-portfolio XLSX")
        try:
            if client is not None:
                resp = await client.post(
                    self.document_url, json=dict(self.document_payload),
                    timeout=self.timeout)
            else:
                async with httpx.AsyncClient(
                        follow_redirects=True) as hc:
                    resp = await hc.post(
                        self.document_url, json=dict(self.document_payload),
                        timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            raise BoiHoldingsError(
                f"BOI document discovery failed: {exc}") from exc
        return extract_document_url(payload)

    async def download_workbook(
        self, url: str, client: httpx.AsyncClient | None = None,
    ) -> bytes:
        """Download XLSX (cached per URL)."""
        if url in self._workbook_cache:
            logger.debug("BOI workbook cache hit")
            return self._workbook_cache[url]
        logger.info("Downloading BOI monthly-portfolio workbook")
        try:
            if client is not None:
                resp = await client.get(url, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(
                        follow_redirects=True) as hc:
                    resp = await hc.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.content
        except Exception as exc:
            raise BoiHoldingsError(
                f"BOI workbook download failed: {exc}") from exc
        if data[:2] != b"PK":
            raise BoiHoldingsError("BOI download is not a valid XLSX file")
        self._workbook_cache[url] = data
        return data

    async def fetch_holdings(
        self,
        selections: Sequence[Any],
        *,
        client: httpx.AsyncClient | None = None,
    ) -> AmfiHoldingsResult:
        """Fetch BOI holdings for selected BOI schemes only."""
        result = AmfiHoldingsResult(quarter="BOI-monthly")
        members: list[tuple[str, str]] = []
        for sel in selections:
            code, name, amc = self._parts(sel)
            if not is_boi_selection(amc):
                continue
            if not code or not name:
                result.unmatched.append({
                    "scheme_code": code, "scheme_name": name,
                    "reason": "missing_scheme_identity"})
                continue
            members.append((code, name))
        if not members:
            return result
        url = await self.discover_xlsx_url(client=client)
        data = await self.download_workbook(url, client=client)
        sheets = read_xlsx_sheets(data)
        index_rows: Sequence[Sequence[str]] = []
        for sheet_name, rows in sheets.items():
            if sheet_name.strip().lower() == "index":
                index_rows = rows
                break
        if not index_rows:
            raise BoiHoldingsError("BOI workbook Index sheet not found")
        index_map = parse_index_sheet(index_rows)
        if not index_map:
            raise BoiHoldingsError("BOI Index sheet has no scheme mapping")
        for code, name in members:
            try:
                sheet_id, _label = resolve_boi_sheet_id(name, index_map)
            except BoiHoldingsError as exc:
                logger.warning("BOI scheme resolution failed: %s", exc)
                result.unmatched.append({
                    "scheme_code": code, "scheme_name": name,
                    "reason": "boi_scheme_not_found"})
                continue
            sheet_rows = sheets.get(sheet_id)
            if sheet_rows is None:
                for key in sheets:
                    if key.strip().upper() == sheet_id.upper():
                        sheet_rows = sheets[key]
                        break
            if not sheet_rows:
                result.unmatched.append({
                    "scheme_code": code, "scheme_name": name,
                    "reason": "boi_sheet_missing"})
                continue
            result.holdings.extend(parse_scheme_sheet_holdings(
                sheet_rows, scheme_code=code, scheme_name=name,
                amfi_scheme_name=name))
        return result
