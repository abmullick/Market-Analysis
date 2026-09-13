"""Minimal tests for the isolated AMFI holdings layer."""
import pytest

from backend.services.data.amfi_holdings import (
    AmfiHoldingsService,
    is_equity_security,
    match_amfi_scheme,
    normalize_holding_row,
    normalize_scheme_name,
    resolve_mf_id,
)


def _row(scheme="LIC MF Aggressive Hybrid Fund", sid="106",
         isin="INE009A01021", company="Infosys Ltd.",
         stype="Investment - Equities", mv=5.5, pct=1.04):
    return {"MF_ID": "18", "Scheme_ID": sid, "Scheme_Name": scheme,
            "ISIN": isin, "Company_Name": company, "Security_Type": stype,
            "MarketValue": mv, "MarketValuePercentage": pct,
            "QuarterDate": "2026-04-01T00:00:00.000Z",
            "QuarterName": "Apr-Jun 2026"}


class TestSchemeNormalization:
    def test_superficial_differences(self):
        assert (normalize_scheme_name("LIC MF Aggressive  Hybrid Fund")
                == normalize_scheme_name("lic mf aggressive hybrid fund"))
        assert (normalize_scheme_name("A & B Fund")
                == normalize_scheme_name("A and B Fund"))
        assert (normalize_scheme_name("ABC Fund - Direct Plan - Growth")
                != normalize_scheme_name("ABC Fund - Regular Plan - Growth"))

    def test_meaningful_terms_preserved(self):
        assert "direct" in normalize_scheme_name("X - Direct Plan - Growth")
        assert "growth" in normalize_scheme_name("X - Direct Plan - Growth")
        assert "idcw" in normalize_scheme_name("X - IDCW")

    def test_unique_match(self):
        rows = [_row(), _row(scheme="LIC MF Arbitrage Fund", sid="107",
                             isin="INE111A01025", company="Container Corp")]
        matched, sid, label = match_amfi_scheme(
            "LIC MF Aggressive Hybrid Fund", rows)
        assert sid == "106" and label == "LIC MF Aggressive Hybrid Fund"

    def test_no_match_returns_none(self):
        matched, sid, label = match_amfi_scheme("No Such Fund", [_row()])
        assert (matched, sid, label) == (None, None, None)

    def test_ambiguous_match_returns_none(self):
        rows = [_row(sid="1"), _row(sid="2")]  # same name, 2 Scheme_IDs
        assert match_amfi_scheme("LIC MF Aggressive Hybrid Fund",
                                 rows) == (None, None, None)

    def test_amc_lookup(self):
        assert resolve_mf_id("LIC Mutual Fund") == "18"
        assert resolve_mf_id("LIC MUTUAL FUND ") == "18"
        assert resolve_mf_id("Unknown AMC XYZ") is None


class TestEquityFilter:
    @pytest.mark.parametrize("stype", [
        "Investment - Equities", "Investment - Equity",
        "Listed Equities - Active",
    ])
    def test_equity_passes(self, stype):
        assert is_equity_security(stype) is True

    @pytest.mark.parametrize("stype", [
        "Investment - Corporate Bonds / Debentures",
        "Government Securities", "Cash & Cash Equivalents",
        "TREPS", "Stock Futures", "Index Options", None, "",
    ])
    def test_non_equity_excluded(self, stype):
        assert is_equity_security(stype) is False


class TestHoldingNormalization:
    def test_field_mapping_and_isin(self):
        h = normalize_holding_row(
            _row(), scheme_code="100", scheme_name="App Name",
            amfi_scheme_id="106", amfi_scheme_name="LIC MF Aggressive Hybrid Fund")
        assert h.scheme_code == "100"
        assert h.amfi_scheme_id == "106"
        assert h.isin == "INE009A01021"  # preserved exactly
        assert h.security_name == "Infosys Ltd."
        assert h.security_type == "Investment - Equities"
        assert h.market_value == 5.5
        assert h.portfolio_weight == 1.04


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.calls = 0

    async def get(self, url, params=None, timeout=None):
        self.calls += 1
        assert params["MF_ID"] == "18"
        return FakeResponse(self._payload)


@pytest.mark.asyncio
async def test_fetch_holdings_mocked_groups_and_filters():
    payload = [_row(),
               _row(isin="INE018A08BE9", company="L&T Finance",
                    stype="Investment - Corporate Bonds / Debentures",
                    mv=7.5, pct=1.4),
               _row(scheme="LIC MF Arbitrage Fund", sid="107",
                    isin="INE111A01025", company="Container Corp")]
    svc = AmfiHoldingsService()
    fake = FakeClient(payload)
    # Two selections, SAME AMC -> one HTTP call (AMC x quarter).
    res = await svc.fetch_holdings(
        [{"scheme_code": "100",
          "scheme_name": "LIC MF Aggressive Hybrid Fund",
          "amc": "LIC Mutual Fund"},
         {"scheme_code": "101",
          "scheme_name": "LIC MF Arbitrage Fund",
          "amc": "LIC Mutual Fund"}],
        client=fake)  # type: ignore[arg-type]
    assert fake.calls == 1
    assert res.quarter == "01-Apr-2026"
    assert res.unmatched == []
    by_code = {}
    for h in res.holdings:
        by_code.setdefault(h.scheme_code, []).append(h)
    # Bond row excluded; equity rows kept with ISIN intact.
    assert [h.isin for h in by_code["100"]] == ["INE009A01021"]
    assert [h.isin for h in by_code["101"]] == ["INE111A01025"]


@pytest.mark.asyncio
async def test_fetch_holdings_unmatched_scheme():
    svc = AmfiHoldingsService()
    fake = FakeClient([_row()])
    res = await svc.fetch_holdings(
        [{"scheme_code": "999", "scheme_name": "Ghost Fund XYZ",
          "amc": "LIC Mutual Fund"}],
        client=fake)  # type: ignore[arg-type]
    assert res.holdings == []
    assert len(res.unmatched) == 1
    assert res.unmatched[0]["reason"] == "no_unique_amfi_scheme_match"
