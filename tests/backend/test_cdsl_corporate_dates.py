"""Tests for CDSL corporate-bond date enforcement."""
from __future__ import annotations
import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import pytest
from backend.models.bonds import CdslCorporateBondPrimaryRawRecord, CdslCorporateBondSecondaryRawRecord, DataType
from backend.services.bonds import bond_service as bond_service_module
from backend.services.bonds.bond_service import BondService
from backend.config.settings import Settings
from backend.services.data.bonds import corporate_cdsl as cdsl_module
from backend.services.data.bonds.corporate_cdsl import CdsCorporateBondClient, CdsCorporateBondLiveError, _cdsl_date_strings, _normalize_heading_text, _report_heading_matches_date


def _make_client() -> CdsCorporateBondClient:
    return CdsCorporateBondClient(settings=Settings(_env_file=None))


class TestCdslDateStrings:
    @pytest.mark.parametrize("given,expected", [
        ("2026-09-17", ("September 17, 2026", "17-Sep-2026")),
        (date(2026, 9, 17), ("September 17, 2026", "17-Sep-2026")),
        (datetime(2026, 9, 17, 15, 30), ("September 17, 2026", "17-Sep-2026")),
        ("17-Sep-2026", ("September 17, 2026", "17-Sep-2026")),
        ("17-09-2026", ("September 17, 2026", "17-Sep-2026")),
    ])
    def test_iso_and_display_inputs(self, given, expected):
        assert _cdsl_date_strings(given) == expected

    def test_unparseable_raises(self):
        with pytest.raises(ValueError):
            _cdsl_date_strings("not-a-date")


class TestHeadingMatching:
    def test_exact_match(self):
        assert _report_heading_matches_date("Secondary Market Trade Data For 17-Sep-2026", "17-Sep-2026")

    def test_whitespace_and_case_insensitive(self):
        assert _report_heading_matches_date("  secondary   market trade data for   17-sep-2026 ", "17-Sep-2026")

    def test_mismatched_date_rejected(self):
        assert not _report_heading_matches_date("Secondary Market Trade Data For 18-Sep-2026", "17-Sep-2026")

    def test_missing_heading_rejected(self):
        assert not _report_heading_matches_date("", "17-Sep-2026")
        assert not _report_heading_matches_date(None, "17-Sep-2026")

    def test_normalize_collapses_whitespace(self):
        assert _normalize_heading_text("a  b\tc\n") == "a b c"


class _FakeTimeout(Exception):
    pass


class _FakeLocator:
    def __init__(self, page, selector):
        self._page = page
        self._selector = selector
    def fill(self, value):
        if self._selector == "#idtradedate":
            self._page.state["visible"] = value
    def select_option(self, value):
        pass
    def input_value(self):
        if self._selector == "#idtradedate":
            return self._page.state.get("visible", "")
        return ""
    def evaluate(self, script, value=None):
        if self._selector == "#idhdndate" and "el.value = value" in script:
            self._page.state["hidden"] = value
        if self._selector == "#idhdndate" and "el.value || ''" in script:
            return self._page.state.get("hidden", "")
        if "Array.from(t.rows)" in script:
            self._page.extracted += 1
            return self._page.state.get("extracted_rows", [[{"text": "BSE", "anchor": None}]])
        return None
    def inner_text(self, timeout=None):
        if self._selector in ("#tradedata", "body"):
            return self._page.state.get("region_text", "")
        return ""
    def click(self):
        self._page.clicks += 1
        if self._page.state.get("click_behavior") == "timeout":
            raise self._page.timeout_error("navigation timeout")
        self._page.state["region_text"] = self._page.state.get("post_heading", "")
    def wait_for(self, state="attached", timeout=30000):
        return None
    def count(self):
        return 1


class _FakePage:
    def __init__(self, state, timeout_error):
        self.state = state
        self.timeout_error = timeout_error
        self.clicks = 0
        self.extracted = 0
    def goto(self, *a, **k):
        return None

    def close(self):
        return None

    def locator(self, selector):
        return _FakeLocator(self, selector)

    def expect_navigation(self, **kwargs):
        page = self

        class _NavCtx:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        return _NavCtx()


class _Harness:
    def __init__(self, states):
        self._states = list(states)
        self.pages = []

    def install(self, monkeypatch, rows_per_attempt=None):
        harness = self

        class _FakeSyncPlaywright:
            def __init__(self):
                self._page = None

            def __enter__(self):
                if len(harness._states) > 1:
                    st = harness._states.pop(0)
                else:
                    st = harness._states[0]
                self._page = _FakePage(dict(st), _FakeTimeout)
                harness.pages.append(self._page)
                return SimpleNamespace(chromium=self)

            def __exit__(self, *a):
                return False

            def launch(self, headless=True):
                page = self._page

                class _Browser:
                    def new_context(self):
                        class _Ctx:
                            def new_page(self):
                                return page
                            def close(self):
                                return None
                        return _Ctx()

                    def close(self):
                        return None

                return _Browser()

        def _fake_sync_playwright():
            return _FakeSyncPlaywright()

        orig_attempt = CdsCorporateBondClient._cdsl_search_rows_attempt

        def _patched_attempt(slf, trade_date, market_type, table_selector,
                             sync_playwright, PlaywrightTimeoutError):
            # Route the real attempt through the fake transport.
            return orig_attempt(
                slf, trade_date, market_type, table_selector,
                _fake_sync_playwright, _FakeTimeout,
            )

        monkeypatch.setattr(
            CdsCorporateBondClient, "_cdsl_search_rows_attempt", _patched_attempt
        )
        return harness


def _ok_state(heading, rows="rows"):
    return {"click_behavior": "ok", "post_heading": heading, "post_rows": rows, "region_text": ""}


def _timeout_state():
    return {"click_behavior": "timeout", "region_text": "September 18, 2026 stale report"}


class TestSearchTimeoutAndHeading:
    def test_timeout_never_scrapes_stale_page(self, monkeypatch):
        h = _Harness([_timeout_state(), _timeout_state()])
        h.install(monkeypatch)
        client = _make_client()
        with pytest.raises(CdsCorporateBondLiveError):
            client._cdsl_search_rows("2026-09-17", "S", "table.tblSecDetails")
        assert len(h.pages) == 2
        assert all(p.extracted == 0 for p in h.pages)

    def test_timeout_then_retry_succeeds(self, monkeypatch):
        h = _Harness([_timeout_state(), _ok_state("Secondary Market Trade Data For 17-Sep-2026")])
        h.install(monkeypatch)
        client = _make_client()
        rows = client._cdsl_search_rows("2026-09-17", "S", "table.tblSecDetails")
        assert rows == [[{"text": "BSE", "anchor": None}]]
        assert len(h.pages) == 2

    def test_mismatched_heading_rejected_then_retry_succeeds(self, monkeypatch):
        h = _Harness([_ok_state("Secondary Market Trade Data For 18-Sep-2026"), _ok_state("Secondary Market Trade Data For 17-Sep-2026")])
        h.install(monkeypatch)
        client = _make_client()
        rows = client._cdsl_search_rows("2026-09-17", "S", "table.tblSecDetails")
        assert rows == [[{"text": "BSE", "anchor": None}]]
        assert len(h.pages) == 2

    def test_persistent_mismatch_raises(self, monkeypatch):
        h = _Harness([_ok_state("Secondary Market Trade Data For 18-Sep-2026"), _ok_state("Secondary Market Trade Data For 18-Sep-2026")])
        h.install(monkeypatch)
        client = _make_client()
        with pytest.raises(CdsCorporateBondLiveError):
            client._cdsl_search_rows("2026-09-17", "S", "table.tblSecDetails")
        assert len(h.pages) == 2

    def test_date_fields_synced_with_events(self, monkeypatch):
        h = _Harness([_ok_state("Secondary Market Trade Data For 17-Sep-2026")])
        h.install(monkeypatch)
        client = _make_client()
        client._cdsl_search_rows("2026-09-17", "S", "table.tblSecDetails")
        assert h.pages[0].state.get("visible") == "September 17, 2026"
        assert h.pages[0].state.get("hidden") == "17-Sep-2026"


def _sec(trade_date, isin):
    return CdslCorporateBondSecondaryRawRecord(exchange="BSE", trade_date=trade_date, isin=isin, listed_unlisted="Listed", issuer_name="Test Issuer Ltd", issue_description="9.00% Test Issuer 2030", coupon_rate_raw="9.00", maturity_date="15-Jun-2030", credit_rating_raw="CRISIL AAA", number_of_trades="2", total_trade_value_raw="10.5", last_traded_price_raw="101.25", vwap_raw="101.20", weighted_average_yield_raw="8.75", remark=None)


def _pri(isin):
    return CdslCorporateBondPrimaryRawRecord(isin=isin, temporary_isin=None, issuer_name="Test Issuer Ltd", issue_description="9.00% Test Issuer 2030", issue_type="Private Placement", issue_size_raw="100", issue_price_raw="100", issue_date="01-Jan-2025", maturity_date="15-Jun-2030", coupon_rate_raw="9.00", mode_of_issuance="EBP")


def _run_refresh(monkeypatch, secondary, primary, requested="2026-09-17"):
    service = BondService()
    service._cache.invalidate()
    fake = SimpleNamespace(fetch_secondary_live=lambda resolved: secondary(resolved) if callable(secondary) else secondary, fetch_primary_live=lambda resolved: primary(resolved) if callable(primary) else primary)
    monkeypatch.setattr(service, "_get_cdsl", lambda: fake)
    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)
    monkeypatch.setattr(bond_service_module.asyncio, "to_thread", _fake_to_thread)
    return service, asyncio.run(service.refresh_corporate_sources(requested))


class TestRefreshDateEnforcement:
    def test_valid_results_cached_under_requested_date(self, monkeypatch):
        service, result = _run_refresh(monkeypatch, [_sec("17-Sep-2026", "INE000A00001")], [])
        assert len(result) == 1
        assert result[0].trade_date == date(2026, 9, 17)
        assert service._cache.get("corporate:2026-09-17") is not None

    def test_mismatched_secondary_rows_excluded(self, monkeypatch):
        service, result = _run_refresh(monkeypatch, [_sec("17-Sep-2026", "INE000A00001"), _sec("18-Sep-2026", "INE000A00002")], [])
        assert {b.isin for b in result} == {"INE000A00001"}
        assert all(b.trade_date == date(2026, 9, 17) for b in result)

    def test_primary_records_exempt(self, monkeypatch):
        service, result = _run_refresh(monkeypatch, [], [_pri("INE000A00003")])
        assert len(result) == 1 and result[0].isin == "INE000A00003"
        assert service._cache.get("corporate:2026-09-17") is not None

    def test_all_mismatched_nothing_cached(self, monkeypatch):
        service, result = _run_refresh(monkeypatch, [_sec("18-Sep-2026", "INE000A00002")], [])
        assert result == []
        assert service._cache.get("corporate:2026-09-17") is None

    def test_failed_fetches_never_cached(self, monkeypatch):
        def _boom(resolved):
            raise CdsCorporateBondLiveError("navigation timed out")
        service, result = _run_refresh(monkeypatch, _boom, _boom)
        assert result == []
        assert service._cache.get("corporate:2026-09-17") is None

    def test_single_failed_fetch_still_caches_verified_side(self, monkeypatch):
        def _boom(resolved):
            raise CdsCorporateBondLiveError("primary failed")
        service, result = _run_refresh(monkeypatch, [_sec("17-Sep-2026", "INE000A00001")], _boom)
        assert len(result) == 1
        assert service._cache.get("corporate:2026-09-17") is not None

    def test_stale_upstream_date_returns_empty_without_poisoning_cache(
        self, monkeypatch
    ):
        """Regression: live CDSL serves the wrong-date report for 2026-09-17.

        Verified live on 2026-09-18 via Playwright against
        https://www.cdslindia.com/corporatebond/CorporateBondReports.aspx:
        requesting trade_date=2026-09-17 renders the heading
        "Secondary Market Trade Data For 18-Sep-2026" with only 18-Sep-2026
        rows (see /tmp/cdsl_live_20260917.html + /tmp/cdsl_live_20260917_region.txt;
        the identical 2026-09-18 request renders byte-identical rows). The
        service must return [] for 2026-09-17 (never leak the wrong date's
        bonds) and must not cache that empty result under either date key.
        """
        service, result = _run_refresh(
            monkeypatch, [_sec("18-Sep-2026", "INE000A00002")], [], requested="2026-09-17"
        )
        assert result == []
        assert service._cache.get("corporate:2026-09-17") is None
        assert service._cache.get("corporate:2026-09-18") is None


def _run_latest(monkeypatch, datasets, anchor=date(2026, 9, 23)):
    """Run the latest-available walk against a per-date CDSL dataset stub.

    ``datasets`` maps an ISO date string to ``{"secondary": [...], "primary":
    [...]}`` raw record lists; a date absent from the mapping yields no records
    (a verified-empty day). Returns ``(service, result, fetched_dates)`` where
    ``fetched_dates`` lists, in order, the dates whose *secondary* report the
    walk actually fetched from CDSL.
    """
    service = BondService()
    service._cache.invalidate()
    fetched: List[date] = []

    def _secondary(resolved):
        fetched.append(resolved)
        return datasets.get(resolved.isoformat(), {}).get("secondary", [])

    def _primary(resolved):
        return datasets.get(resolved.isoformat(), {}).get("primary", [])

    fake = SimpleNamespace(
        fetch_secondary_live=_secondary,
        fetch_primary_live=_primary,
    )
    monkeypatch.setattr(service, "_get_cdsl", lambda: fake)

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(bond_service_module.asyncio, "to_thread", _fake_to_thread)
    result = asyncio.run(service._refresh_corporate_latest_available(anchor))
    return service, result, fetched


# 2026-09-23 is a Wednesday and 2026-09-22 the preceding business day: the
# live CDSL asymmetry (issuance-only partial day vs the complete previous
# business-day report) reproduced deterministically.
_TODAY = date(2026, 9, 23)
_PREVIOUS = date(2026, 9, 22)


class TestLatestAvailableCompleteness:
    """A primary-only partial day must not shadow the last complete report."""

    def test_complete_dataset_returned_immediately(self, monkeypatch):
        datasets = {
            _TODAY.isoformat(): {
                "secondary": [_sec("23-Sep-2026", "INE000A00001")],
            },
            _PREVIOUS.isoformat(): {
                "secondary": [_sec("22-Sep-2026", "INE000A00002")],
            },
        }
        service, result, fetched = _run_latest(monkeypatch, datasets)
        assert [b.isin for b in result] == ["INE000A00001"]
        assert all(b.trade_date == _TODAY for b in result)
        # The complete dataset short-circuits the walk: nothing older is probed.
        assert fetched == [_TODAY]
        assert service._cache.get("corporate:2026-09-23") is not None

    def test_issuance_only_day_defers_to_previous_complete_dataset(
        self, monkeypatch
    ):
        """Live 2026-09-23 case: 9 issuance-only rows must not be treated as
        the latest usable universe while 2026-09-22 holds 934 secondary-market
        records."""
        today_primary = [_pri(f"INE000A1{i:04d}") for i in range(9)]
        previous_secondary = [
            _sec("22-Sep-2026", f"INE000B1{i:04d}") for i in range(934)
        ]
        datasets = {
            _TODAY.isoformat(): {"secondary": [], "primary": today_primary},
            _PREVIOUS.isoformat(): {"secondary": previous_secondary, "primary": []},
        }
        service, result, fetched = _run_latest(monkeypatch, datasets)
        assert len(result) == 934
        assert all(b.trade_date == _PREVIOUS for b in result)
        assert all(b.data_type == DataType.TRADED for b in result)
        assert {b.isin for b in result} & {b.isin for b in today_primary} == set()
        # Both days were probed; the complete day won.
        assert fetched == [_TODAY, _PREVIOUS]

    def test_unavailable_day_falls_back_to_earlier_complete_dataset(
        self, monkeypatch
    ):
        datasets = {
            _TODAY.isoformat(): {"secondary": [], "primary": []},
            _PREVIOUS.isoformat(): {
                "secondary": [_sec("22-Sep-2026", "INE296A07TC9")],
            },
        }
        service, result, fetched = _run_latest(monkeypatch, datasets)
        assert [b.isin for b in result] == ["INE296A07TC9"]
        assert all(b.trade_date == _PREVIOUS for b in result)
        assert fetched == [_TODAY, _PREVIOUS]
        # Verified-empty day keeps its existing cache contract and is skipped.
        assert service._cache.get("corporate:2026-09-23") == []

    def test_issuance_only_dataset_served_when_no_complete_dataset_exists(
        self, monkeypatch
    ):
        today_primary = [_pri(f"INE000A1{i:04d}") for i in range(9)]
        datasets = {
            _TODAY.isoformat(): {"secondary": [], "primary": today_primary},
        }
        service, result, fetched = _run_latest(monkeypatch, datasets)
        assert len(result) == 9
        assert {b.isin for b in result} == {b.isin for b in today_primary}
        assert all(b.data_type == DataType.REFERENCE for b in result)
        # The whole lookback window was walked before falling back.
        assert len(fetched) == bond_service_module._CORPORATE_LATEST_LOOKBACK_DAYS

    def test_no_records_anywhere_returns_empty(self, monkeypatch):
        service, result, fetched = _run_latest(monkeypatch, {})
        assert result == []
        assert len(fetched) == bond_service_module._CORPORATE_LATEST_LOOKBACK_DAYS
