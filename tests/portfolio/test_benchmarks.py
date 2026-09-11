"""Tests for the Portfolio vs Benchmark comparison (Phase 2E).

The builder performs live network fetches in production, so these tests monkey-
patch the low-level fetchers to keep them network-free while exercising the
date alignment, INR conversion, rebase-to-100, CAGR and outperformance logic.
"""

import pytest

from backend.models.portfolio import PortfolioSeriesPoint
from backend.services.data import benchmarks as bm
from backend.services.data.benchmarks import BenchmarkProviderError


DATES = [
    "2013-01-08",
    "2013-01-09",
    "2013-01-10",
    "2013-01-11",
    "2013-01-14",
    "2013-01-15",
]
PORT_VALUES = [100.0, 102.0, 103.0, 105.0, 106.0, 110.0]


def _series() -> list[PortfolioSeriesPoint]:
    return [PortfolioSeriesPoint(date=d, value=v) for d, v in zip(DATES, PORT_VALUES)]


@pytest.fixture(autouse=True)
def _clear_cache():
    with bm._cache_lock:
        bm._cache.clear()
    yield
    with bm._cache_lock:
        bm._cache.clear()


def test_all_three_rebased_to_100_with_inr_conversion(monkeypatch):
    nifty = {d: 8000 + i * 100 for i, d in enumerate(DATES)}
    sp_usd = {d: 1000 + i * 10 for i, d in enumerate(DATES)}
    fx = {d: 60.0 + i * 0.5 for i, d in enumerate(DATES)}

    monkeypatch.setattr(bm, "fetch_nifty50_tri", lambda f, t: nifty)
    monkeypatch.setattr(bm, "fetch_sp500_total_return", lambda f, t: sp_usd)
    monkeypatch.setattr(bm, "fetch_usd_inr", lambda f, t: fx)

    bd = bm.build_benchmark_data(_series())

    assert bd.available is True
    assert bd.nifty50_tri_available is True
    assert bd.sp500_available is True
    assert bd.common_start == DATES[0]
    assert bd.common_end == DATES[-1]
    assert bd.observations == len(DATES)

    assert bd.dates == DATES
    assert len(bd.portfolio) == len(DATES)
    assert len(bd.nifty50_tri) == len(DATES)
    assert len(bd.sp500_total_return_inr) == len(DATES)

    # Every series rebased to 100 at the first common date.
    assert bd.portfolio[0] == pytest.approx(100.0)
    assert bd.nifty50_tri[0] == pytest.approx(100.0)
    assert bd.sp500_total_return_inr[0] == pytest.approx(100.0)

    # S&P is converted into INR: usd * fx (prior-or-equal to the date), then
    # rebased to 100. Verify the rebased ratio equals the raw USD*FX ratio.
    raw_inr = [sp_usd[d] * fx[d] for d in DATES]
    assert bd.sp500_total_return_inr[1] == pytest.approx(
        (raw_inr[1] / raw_inr[0]) * 100.0
    )

    # CAGR / outperformance are present and consistent.
    assert bd.portfolio_cagr is not None
    assert bd.nifty50_tri_cagr is not None
    assert bd.sp500_total_return_cagr is not None
    assert bd.nifty50_outperformance == pytest.approx(bd.portfolio_cagr - bd.nifty50_tri_cagr)
    assert bd.sp500_outperformance == pytest.approx(bd.portfolio_cagr - bd.sp500_total_return_cagr)


def test_sp500_failure_degrades_to_two_lines(monkeypatch):
    nifty = {d: 8000 + i * 100 for i, d in enumerate(DATES)}
    monkeypatch.setattr(bm, "fetch_nifty50_tri", lambda f, t: nifty)

    def boom(f, t):
        raise BenchmarkProviderError("S&P 500 TR (Yahoo ^SP500TR) request failed: 429 Too Many Requests")

    monkeypatch.setattr(bm, "fetch_sp500_total_return", boom)

    bd = bm.build_benchmark_data(_series())

    assert bd.available is True
    assert bd.nifty50_tri_available is True
    assert bd.sp500_available is False
    assert len(bd.sp500_total_return_inr) == 0
    assert bd.sp500_total_return_cagr is None
    assert bd.sp500_outperformance is None
    assert any("S&P 500" in w for w in bd.warnings)
    assert bd.portfolio[0] == pytest.approx(100.0)
    assert bd.nifty50_tri[0] == pytest.approx(100.0)


def test_all_benchmarks_unavailable_returns_unavailable(monkeypatch):
    def boom(f, t):
        raise BenchmarkProviderError("down")

    monkeypatch.setattr(bm, "fetch_nifty50_tri", boom)
    monkeypatch.setattr(bm, "fetch_sp500_total_return", boom)

    bd = bm.build_benchmark_data(_series())

    assert bd.available is False
    assert bd.dates == []
    assert bd.portfolio == []
    assert bd.observations == 0


def test_tri_series_is_used_for_nifty(monkeypatch):
    # Confirms NIFTY uses the Total Return Index (TRI), not the price index.
    # Here we just assert the nifty axis is rebased from the supplied TRI values.
    nifty = {d: 1000 + i * 50 for i, d in enumerate(DATES)}
    monkeypatch.setattr(bm, "fetch_nifty50_tri", lambda f, t: nifty)
    monkeypatch.setattr(bm, "fetch_sp500_total_return", lambda f, t: {})
    monkeypatch.setattr(bm, "fetch_usd_inr", lambda f, t: {})

    bd = bm.build_benchmark_data(_series())

    assert bd.available is True
    assert bd.nifty50_tri_available is True
    assert bd.sp500_available is False
    assert bd.nifty50_tri[0] == pytest.approx(100.0)
    assert bd.nifty50_tri[-1] == pytest.approx(125.0)  # (1000 + 5*50)/1000 * 100