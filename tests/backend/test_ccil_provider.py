"""Tests for the CCIL Market Watch provider (NDS-OM portlet JSON).

The current public CCIL Market Watch page

    https://www.ccilindia.com/market-watch

is backed by the Liferay portlet
``com_ccil_ndsom_marketwatch_CcilNDSOMMarketWatchPortlet_INSTANCE_swas``
and is served through the portlet resource mechanism the page's own
JavaScript uses. Three resource IDs back the three sections:

    NDSOMCG       -> Central Government Securities (G-Secs)
    NDSOMSG       -> State Government Securities (SDLs)
    NDSOM_TBILL   -> Treasury Bills

Each resource returns a JSON wrapper ``{"result1": "<json-encoded list>"}``.

These tests parse the REAL responses captured during diagnosis (stored
under ``tests/data/fixtures/ccil/``) and assert the full
CCIL JSON -> CcilRawRecord -> Bond path. No test depends on live
internet access.

Fixture provenance:
  central_market_watch.json  — live NDSOMCG     response (42 records)
  state_market_watch.json    — live NDSOMSG     response (24 records)
  tbill_market_watch.json    — live NDSOM_TBILL response (12 records)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from backend.models.bonds import (
    CcilRawRecord,
    DataType,
    InstrumentType,
)
from backend.services.bonds.bond_normalizer import (
    normalize_ccil_record,
)
from backend.services.data.bonds.ccil import (
    CENTRAL_MARKET_WATCH_URL,
    STATE_MARKET_WATCH_URL,
    TBILL_MARKET_WATCH_URL,
    CcilParseError,
    _num,
    _parse_ccil_json,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "ccil"


def _load(name: str) -> str:
    """Return the raw (verbatim) captured CCIL response text."""
    return (FIXTURE_DIR / name).read_text()


def _raw_rows(name: str) -> list[dict]:
    """Return the decoded record list from a captured response."""
    return json.loads(json.loads(_load(name))["result1"])


# =========================================================================
# Endpoint / resource-ID wiring
# =========================================================================

class TestCcilEndpoints:
    """The provider must target the current portlet resource mechanism."""

    def test_does_not_use_obsolete_flow_html_url(self):
        """The obsolete /market/watch/.../flow.html path is never used."""
        for url in (
            CENTRAL_MARKET_WATCH_URL,
            STATE_MARKET_WATCH_URL,
            TBILL_MARKET_WATCH_URL,
        ):
            assert "/market/watch/" not in url
            assert "flow.html" not in url

    def test_uses_market_watch_portlet(self):
        """All three sections use the current Market Watch portlet."""
        for url in (
            CENTRAL_MARKET_WATCH_URL,
            STATE_MARKET_WATCH_URL,
            TBILL_MARKET_WATCH_URL,
        ):
            assert url.startswith("https://www.ccilindia.com/market-watch?")
            assert (
                "p_p_id=com_ccil_ndsom_marketwatch_"
                "CcilNDSOMMarketWatchPortlet_INSTANCE_swas"
            ) in url
            assert "p_p_lifecycle=2" in url

    def test_resource_ids(self):
        """The verified resource IDs are used for each section."""
        assert "p_p_resource_id=NDSOMCG" in CENTRAL_MARKET_WATCH_URL
        assert "p_p_resource_id=NDSOMSG" in STATE_MARKET_WATCH_URL
        assert "p_p_resource_id=NDSOM_TBILL" in TBILL_MARKET_WATCH_URL


# =========================================================================
# JSON wrapper parsing
# =========================================================================

class TestCcilJsonWrapper:
    """The ``result1`` wrapper must be parsed per section."""

    def test_central_fixture_extracts_rows(self):
        recs = _parse_ccil_json(_load("central_market_watch.json"), "central")
        assert len(recs) == 42
        assert all(isinstance(r, CcilRawRecord) for r in recs)

    def test_state_fixture_extracts_rows(self):
        recs = _parse_ccil_json(_load("state_market_watch.json"), "state")
        assert len(recs) == 24

    def test_tbill_fixture_extracts_rows(self):
        recs = _parse_ccil_json(_load("tbill_market_watch.json"), "tbills")
        assert len(recs) == 12

    def test_result1_as_already_decoded_list(self):
        """result1 may arrive already decoded rather than JSON-encoded."""
        payload = json.dumps({"result1": _raw_rows("tbill_market_watch.json")})
        recs = _parse_ccil_json(payload, "tbills")
        assert len(recs) == 12

    def test_known_gsec_is_parsed(self):
        """A known live G-Sec is parsed with all market fields."""
        recs = _parse_ccil_json(_load("central_market_watch.json"), "central")
        by_desc = {r.security_description: r for r in recs}
        assert "06.94 GS 2036" in by_desc

        rec = by_desc["06.94 GS 2036"]
        assert rec.section == "central"
        assert rec.maturity_date == "11/05/2036"
        # Central/state source keys are swapped; raw fields carry semantic values.
        assert rec.ltp == "99.07000000"
        assert rec.lty == "7.07270000"
        assert rec.lta == "10.0000000000000000"
        assert rec.tta == "33590.000000000000"
        assert rec.isin is None

    def test_security_description_is_whitespace_normalised(self):
        """CCIL pads descriptions; the stored value is trimmed/normalised."""
        recs = _parse_ccil_json(_load("central_market_watch.json"), "central")
        for rec in recs:
            assert rec.security_description == rec.security_description.strip()
            assert "  " not in rec.security_description

    def test_unknown_auxiliary_columns_are_not_mapped(self):
        """The zero-filled a-f columns never leak into mapped fields."""
        recs = _parse_ccil_json(_load("central_market_watch.json"), "central")
        rec = next(r for r in recs if r.security_description == "06.94 GS 2036")
        # a-f are all "0.0000..." in the live payload; none of these
        # mapped fields should have picked up such a value as a real price.
        assert rec.bid_price is None
        assert rec.bid_yield is None
        assert rec.offer_price is None
        assert rec.offer_yield is None
        assert rec.bid_amount is None
        assert rec.offer_amount is None


# =========================================================================
# Resource endpoint discovery
# =========================================================================

class TestCcilResourceEndpoints:
    """The provider must use the CURRENT portlet resource mechanism."""

    def test_resource_ids_are_the_current_page_resources(self):
        """Central/State/T-Bill resource IDs come from the live page JS."""
        assert "p_p_resource_id=NDSOMCG" in CENTRAL_MARKET_WATCH_URL
        assert "p_p_resource_id=NDSOMSG" in STATE_MARKET_WATCH_URL
        assert "p_p_resource_id=NDSOM_TBILL" in TBILL_MARKET_WATCH_URL

    def test_uses_current_portlet(self):
        """All three resources target the current Market Watch portlet."""
        for url in (
            CENTRAL_MARKET_WATCH_URL,
            STATE_MARKET_WATCH_URL,
            TBILL_MARKET_WATCH_URL,
        ):
            assert url.startswith("https://www.ccilindia.com/market-watch?")
            assert (
                "com_ccil_ndsom_marketwatch_CcilNDSOMMarketWatchPortlet"
                " INSTANCE_swas".replace(" ", "_")
            ) in url
            assert "p_p_lifecycle=2" in url

    def test_obsolete_flow_html_path_not_used(self):
        """The obsolete .../market/watch/.../flow.html path must be gone."""
        for url in (
            CENTRAL_MARKET_WATCH_URL,
            STATE_MARKET_WATCH_URL,
            TBILL_MARKET_WATCH_URL,
        ):
            assert "flow.html" not in url
            assert "/market/watch/" not in url


# =========================================================================
# JSON wrapper parsing
# =========================================================================

class TestCcilJsonWrapperParsing:
    """CCIL returns {"result1": "<json-encoded list>"}."""

    def test_central_fixture_parses(self):
        """The captured Central Government response yields 42 records."""
        records = _parse_ccil_json(_load("central_market_watch.json"), "central")
        assert len(records) == 42
        assert len(_raw_rows("central_market_watch.json")) == 42

    def test_state_fixture_parses(self):
        """The captured State Government response yields 24 records."""
        records = _parse_ccil_json(_load("state_market_watch.json"), "state")
        assert len(records) == 24

    def test_tbill_fixture_parses(self):
        """The captured T-Bill response yields 12 records."""
        records = _parse_ccil_json(_load("tbill_market_watch.json"), "tbills")
        assert len(records) == 12

    def test_result1_already_decoded_list(self):
        """result1 may arrive as an already-parsed list, not a string."""
        text = json.dumps({"result1": _raw_rows("tbill_market_watch.json")})
        records = _parse_ccil_json(text, "tbills")
        assert len(records) == 12
        assert records[0].security_description == "182 DTB 18092026"

    def test_invalid_json_raises_parse_error(self):
        """Non-JSON payloads raise CcilParseError (not an empty list)."""
        with pytest.raises(CcilParseError):
            _parse_ccil_json("<html>Service Unavailable</html>", "central")

    def test_missing_result1_raises_parse_error(self):
        """A schema change (no result1) raises rather than silently empty."""
        with pytest.raises(CcilParseError):
            _parse_ccil_json(json.dumps({"result2": "[]"}), "central")

    def test_result1_not_a_list_raises_parse_error(self):
        """result1 decoding to a non-list raises CcilParseError."""
        with pytest.raises(CcilParseError):
            _parse_ccil_json(json.dumps({"result1": {"not": "a list"}}), "central")

    def test_result1_bad_json_string_raises_parse_error(self):
        """A malformed JSON-encoded result1 string raises CcilParseError."""
        with pytest.raises(CcilParseError):
            _parse_ccil_json(json.dumps({"result1": "{not json"}), "central")

    def test_non_object_wrapper_raises_parse_error(self):
        """A JSON array at the top level raises CcilParseError."""
        with pytest.raises(CcilParseError):
            _parse_ccil_json("[]", "central")

    def test_empty_result1_returns_empty_list(self):
        """An empty (but valid) table is not an error."""
        records = _parse_ccil_json(json.dumps({"result1": "[]"}), "central")
        assert records == []

    def test_rows_without_description_are_skipped(self):
        """Rows with no recognisable security description are skipped."""
        payload = [
            {"ismt_idnt": "06.94 GS 2036", "mrty_date": "11/05/2036"},
            {"ismt_idnt": "", "mrty_date": "11/05/2036"},
            {"ismt_idnt": None, "mrty_date": "11/05/2036"},
            "not-a-dict",
        ]
        records = _parse_ccil_json(json.dumps({"result1": json.dumps(payload)}), "central")
        assert len(records) == 1
        assert records[0].security_description == "06.94 GS 2036"
