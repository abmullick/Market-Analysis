"""Focused BOI fallback adapter tests (all BOI I/O mocked)."""
import io
import zipfile
from xml.sax.saxutils import escape as xml_escape

import pytest

from backend.services.data.boi_holdings import (
    BoiHoldingsAdapter,
    boi_short_name,
    extract_document_url,
    is_boi_non_equity_name,
    normalize_isin,
    parse_index_sheet,
    parse_scheme_sheet_holdings,
    resolve_boi_sheet_id,
)

HEADER = ["Name of the Instrument", "ISIN", "Industry / Rating", "Quantity",
          "Market/Fair Value (Rs. in Lacs)", "% to Net Assets", "YTM"]

INDEX_ROWS = [
    ["Sheet", "Scheme Name"],
    ["YB04", "Bank of India Large & Mid Cap Fund (An open ended equity "
             "scheme investing in both large cap and mid cap stocks)"],
    ["YB07", "Bank of India Small Cap Fund (An open ended equity scheme)"],
]

YB04_ROWS = [
    ["Name of Mutual Fund : Bank of India Mutual Fund"],
    ["Bank of India Large & Mid Cap Fund (...)"],
    HEADER,
    ["Equity & Equity related", "", "", "", "", "", ""],
    ["(a) Listed / awaiting listing on Stock Exchanges",
     "", "", "", "", "", ""],
    ["HDFC Bank Limited", "INE040A01034", "Banks", "556587", "3946.2",
     "0.0746", ""],
    ["Treasury Bills 91 DTB", "IN002025X123", "Sovereign", "1000", "99.1",
     "0.5", ""],
    ["TREPS", "", "Cash", "0", "500.0", "1.2", ""],
    ["Net Receivables / Payables", "", "", "", "10.0", "0.1", ""],
    ["Equity Subtotal", "", "", "", "3946.2", "7.46", ""],
]

YB07_ROWS = [
    ["Name of Mutual Fund : Bank of India Mutual Fund"],
    ["Bank of India Small Cap Fund (...)"],
    HEADER,
    ["Equity & Equity related", "", "", "", "", "", ""],
    ["Small Co Ltd", "INE999A01011", "Chemicals", "100", "50.0", "2.0", ""],
    ["Money Market Instruments", "", "", "", "", "", ""],
    ["Certificate of Deposit", "INECDL123456", "Banks", "10", "9.9",
     "0.4", ""],
]
def _xlsx_bytes(sheets: dict[str, list[list[str]]]) -> bytes:
    strings: list[str] = []
    index_of: dict[str, int] = {}

    def s_idx(value: str) -> int:
        if value not in index_of:
            index_of[value] = len(strings)
            strings.append(value)
        return index_of[value]

    def col_name(n: int) -> str:
        name = ""
        n += 1
        while n:
            n, rem = divmod(n - 1, 26)
            name = chr(65 + rem) + name
        return name

    sheet_xml: dict[str, str] = {}
    for pos, (sname, rows) in enumerate(sheets.items()):
        cells = []
        for r, row in enumerate(rows, start=1):
            parts = []
            for c, val in enumerate(row):
                text = "" if val is None else str(val)
                if text == "":
                    continue
                ref = f"{col_name(c)}{r}"
                parts.append(
                    f'<c r="{ref}" t="s"><v>{s_idx(text)}</v></c>')
            cells.append(f"<row r=\"{r}\">{''.join(parts)}</row>")
        sheet_xml[f"sheet{pos + 1}.xml"] = (
            '<?xml version="1.0"?><worksheet xmlns='
            '"http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(cells)}</sheetData></worksheet>")

    sst = "".join(f"<si><t>{xml_escape(s)}</t></si>" for s in strings)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sharedStrings.xml",
                    '<?xml version="1.0"?><sst xmlns='
                    '"http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    f"{sst}</sst>")
        sheets_el = "".join(
            f'<sheet name="{xml_escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
            for i, n in enumerate(sheets))
        zf.writestr("xl/workbook.xml",
                    '<?xml version="1.0"?><workbook xmlns='
                    '"http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument'
                    '/2006/relationships">'
                    f"<sheets>{sheets_el}</sheets></workbook>")
        rels = "".join(
            f'<Relationship Id="rId{i + 1}" Type='
            '"http://schemas.openxmlformats.org/officeDocument/2006/'
            f'relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
            for i in range(len(sheets)))
        zf.writestr("xl/_rels/workbook.xml.rels",
                    '<?xml version="1.0"?><Relationships xmlns='
                    '"http://schemas.openxmlformats.org/package/2006/'
                    f'relationships">{rels}</Relationships>')
        for fname, xml in sheet_xml.items():
            zf.writestr(f"xl/worksheets/{fname}", xml)
    return buf.getvalue()


def test_rel_id_mapping_ignores_rels_order():
    """Names must resolve via r:id even when .rels order is shuffled."""
    from backend.services.data.boi_holdings import read_xlsx_sheets

    ordered = ["Index", "YB01", "YB04"]
    xlsx = _xlsx_bytes({n: [[f"MARKER-{n}"]] for n in ordered})

    # Rewrite the archive with .rels entries in REVERSE order while
    # keeping workbook sheet order + r:id -> target mapping intact.
    import zipfile as _zf

    src = _zf.ZipFile(io.BytesIO(xlsx))
    entries = {name: src.read(name) for name in src.namelist()}
    from xml.etree import ElementTree as _ET

    rels_root = _ET.fromstring(entries["xl/_rels/workbook.xml.rels"])
    children = list(rels_root)
    for child in children:
        rels_root.remove(child)
    for child in reversed(children):
        rels_root.append(child)
    entries["xl/_rels/workbook.xml.rels"] = _ET.tostring(
        rels_root, xml_declaration=True, encoding="utf-8")
    buf = io.BytesIO()
    with _zf.ZipFile(buf, "w", _zf.ZIP_DEFLATED) as out:
        for name, data in entries.items():
            out.writestr(name, data)
    shuffled = buf.getvalue()

    sheets = read_xlsx_sheets(shuffled)
    assert sheets["Index"] == [["MARKER-Index"]]
    assert sheets["YB01"] == [["MARKER-YB01"]]
    assert sheets["YB04"] == [["MARKER-YB04"]]


class TestBoiSchemeMatching:
    def test_parenthetical_ignored(self):
        assert boi_short_name(
            "Bank of India Large & Mid Cap Fund (An open ended scheme)"
        ) == boi_short_name("BANK OF INDIA LARGE & MID CAP FUND")

    def test_index_resolution_yb04(self):
        index = parse_index_sheet(INDEX_ROWS)
        assert index["YB04"].startswith("Bank of India Large")
        sid, label = resolve_boi_sheet_id(
            "BANK OF INDIA LARGE & MID CAP FUND", index)
        assert sid == "YB04"
        assert "Large & Mid Cap" in label

    def test_unresolvable_scheme_raises(self):
        index = parse_index_sheet(INDEX_ROWS)
        with pytest.raises(Exception):
            resolve_boi_sheet_id("BANK OF INDIA GHOST FUND XYZ", index)


class TestBoiEquityExtraction:
    def test_equity_rows_and_exclusions(self):
        holdings = parse_scheme_sheet_holdings(
            YB04_ROWS, scheme_code="BOI1", scheme_name="BOI Large & Mid",
            amfi_scheme_name="BANK OF INDIA LARGE & MID CAP FUND")
        assert [h.isin for h in holdings] == ["INE040A01034"]
        hdfc = holdings[0]
        assert hdfc.security_name == "HDFC Bank Limited"
        assert hdfc.portfolio_weight == pytest.approx(0.0746)
        assert hdfc.market_value == pytest.approx(3946.2)
        assert hdfc.scheme_code == "BOI1"
        assert "equity" in hdfc.security_type.lower()

    def test_name_and_isin_helpers(self):
        assert is_boi_non_equity_name("Treasury Bills 91 DTB")
        assert is_boi_non_equity_name("TREPS")
        assert is_boi_non_equity_name("Net Receivables / Payables")
        assert not is_boi_non_equity_name("HDFC Bank Limited")
        assert normalize_isin(" ine040a01034 ") == "INE040A01034"
        assert normalize_isin("TREPS") == ""
        assert normalize_isin("") == ""
class FakeResp:
    def __init__(self, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeBoiClient:
    def __init__(self, xlsx: bytes, url: str):
        self._xlsx = xlsx
        self._url = url
        self.posts = 0
        self.gets = 0

    async def post(self, url, json=None, timeout=None):
        self.posts += 1
        return FakeResp(payload={"Documents": [{"DocumentUrl": self._url}]})

    async def get(self, url, timeout=None):
        self.gets += 1
        return FakeResp(content=self._xlsx)


@pytest.mark.asyncio
async def test_shared_download_across_boi_schemes():
    xlsx = _xlsx_bytes({"Index": INDEX_ROWS, "YB04": YB04_ROWS,
                        "YB07": YB07_ROWS})
    url = "https://www.boimf.in/docs/monthly-portfolio.xlsx"
    fake = FakeBoiClient(xlsx, url)
    adapter = BoiHoldingsAdapter()
    selections = [
        {"scheme_code": "B1",
         "scheme_name": "BANK OF INDIA LARGE & MID CAP FUND",
         "amc": "Bank of India Mutual Fund"},
        {"scheme_code": "B2",
         "scheme_name": "BANK OF INDIA SMALL CAP FUND",
         "amc": "Bank of India Mutual Fund"},
        {"scheme_code": "H1", "scheme_name": "HDFC Flexi Cap Fund",
         "amc": "HDFC Mutual Fund"},
    ]
    result = await adapter.fetch_holdings(selections, client=fake)
    assert fake.posts == 1
    assert fake.gets == 1
    assert result.unmatched == []
    by_code = {}
    for h in result.holdings:
        by_code.setdefault(h.scheme_code, []).append(h.isin)
    assert by_code["B1"] == ["INE040A01034"]
    assert by_code["B2"] == ["INE999A01011"]
    assert "H1" not in by_code


@pytest.mark.asyncio
async def test_unknown_scheme_unmatched():
    xlsx = _xlsx_bytes({"Index": INDEX_ROWS, "YB04": YB04_ROWS})
    fake = FakeBoiClient(xlsx, "https://www.boimf.in/docs/m.xlsx")
    adapter = BoiHoldingsAdapter()
    result = await adapter.fetch_holdings(
        [{"scheme_code": "B9",
          "scheme_name": "BANK OF INDIA GHOST FUND XYZ",
          "amc": "Bank of India Mutual Fund"}],
        client=fake)
    assert result.holdings == []
    assert len(result.unmatched) == 1
    assert result.unmatched[0]["reason"] == "boi_scheme_not_found"


def test_extract_document_url_variants():
    url = "https://www.boimf.in/docs/a/monthly-portfolio.xlsx?sfvrsn=1"
    assert extract_document_url(
        {"Documents": [{"DocumentUrl": url}]}) == url
    assert extract_document_url(
        {"d": {"Documents": [{"Url": url}]}}) == url
