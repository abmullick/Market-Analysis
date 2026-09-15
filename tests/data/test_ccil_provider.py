"""CCIL Market Watch provider tests (JSON portlet-resource mechanism).

Baseline provenance
-------------------
These fixtures are REAL captured responses. They were captured from the
live CCIL Market Watch portlet resources on 2026-09-15:

    central_market_watch.json  <- p_p_resource_id=NDSOMCG
    state_market_watch.json    <- p_p_resource_id=NDSOMSG
    tbill_market_watch.json    <- p_p_resource_id=NDSOM_TBILL

``central_market_watch.json`` is byte-identical to the response originally
captured as ``/tmp/ccil_mw2.html`` during diagnosis. The fixtures live in
the repository so that no test depends on ``/tmp`` or on live internet.
No fixture data is fabricated.

Covers:
  - JSON wrapper parsing (``result1`` as JSON-encoded string and as a list)
  - real Central Government / State / T-Bill record extraction
  - maturity / LTP / LTY / LTA / TTA field mapping
  - section-aware price/yield semantics (the Central/State JSON field names
    are swapped relative to the rendered LTP/LTY columns)
  - coupon extraction from CCIL security descriptions
  - missing ISIN stays None (no fabrication)
  - null / blank / zero numeric handling
  - provider error isolation and CcilParseError behaviour
  - Bond normalizer output for real records
  - BondService integration and cache behaviour (no live internet)
  - GET /api/bonds returning CCIL-derived records
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.bonds import (
    Bond,
    CcilRawRecord,
    DataType,
    InstrumentType,
)
from backend.routes import bonds as bonds_routes
from backend.services.bonds.bond_normalizer import (
    _coupon_from_ccil_description,
    normalize_ccil_record,
)
from backend.services.bonds.bond_service import BondCache, BondService
from backend.services.data.bonds import ccil as ccil_mod
from backend.services.data.bonds.ccil import (
    CENTRAL_MARKET_WATCH_URL,
    STATE_MARKET_WATCH_URL,
    TBILL_MARKET_WATCH_URL,
    CcilParseError,
    _num,
    _parse_ccil_json,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ccil"

CENTRAL_FIXTURE = FIXTURE_DIR / "central_market_watch.json"
STATE_FIXTURE = FIXTURE_DIR / "state_market_watch.json"
TBILL_FIXTURE = FIXTURE_DIR / "tbill_market_watch.json"


def _fixture_text(path: Path) -> str:
    assert path.is_file(), f"missing CCIL fixture: {path}"
    return path.read_text()


def _fixture_rows(path: Path) -> list[dict]:
    wrapper = json.loads(_fixture_text(path))
    return json.loads(wrapper["result1"])


# =========================================================================
# Endpoint / resource mechanism
# =========================================================================

class TestCcilResourceEndpoints:
    """The current portlet resource mechanism and its resource ids."""

    def test_central_resource_id(self):
        assert "p_p_resource_id=NDSOMCG" in CENTRAL_MARKET_WATCH_URL

    def test_state_resource_id(self):
        assert "p_p_resource_id=NDSOMSG" in STATE_MARKET_WATCH_URL

    def test_tbill_resource_id(self):
        assert "p_p_resource_id=NDSOM_TBILL" in TBILL_MARKET_WATCH_URL

    def test_portlet_resource_mechanism(self):
        """Resource URLs use the page's own portlet lifecycle=2 mechanism."""
        for url in (
            CENTRAL_MARKET_WATCH_URL,
            STATE_MARKET_WATCH_URL,
            TBILL_MARKET_WATCH_URL,
        ):
            assert url.startswith("https://www.ccilindia.com/market-watch?")
            assert "p_p_lifecycle=2" in url
            assert (
                "com_ccil_ndsom_marketwatch_"
                "CcilNDSOMMarketWatchPortlet_INSTANCE_swas" in url
            )

    def test_obsolete_url_not_used(self):
        """The obsolete /market/watch/.../flow.html path is gone."""
        module_source = Path(ccil_mod.__file__).read_text()
        assert "/market/watch/" not in module_source
        for url in (
            CENTRAL_MARKET_WATCH_URL,
            STATE_MARKET_WATCH_URL,
            TBILL_MARKET_WATCH_URL,
        ):
            assert "flow.html" not in url
