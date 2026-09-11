"""Tests for the additive Drawdown & Recovery analysis.

Methodology under test (see ``backend/services/portfolio/mf_analysis.py``):

    drawdown(t) = value(t) / running_peak(t) - 1

An episode begins when the portfolio moves below its previous running peak
and ends (recovers) when it reaches or exceeds that peak — the same
running-peak convention as the existing ``MetricsCalculator._max_drawdown``
(peak-to-trough magnitude ``(peak - value) / peak``, positive). Durations
are calendar-day differences. Ongoing episodes (still below the previous
peak at the last observation) have no recovery date/durations.

Reconciliation invariant (tested):

    min(episode.drawdown) == -metrics.maximum_drawdown  (within 1e-9)

since both derive from the same running-peak series.
"""

from datetime import date, timedelta

import pytest

from backend.models.mutual_fund import NAVRecord
from backend.services.portfolio.mf_analysis import (
    calculate_drawdown_recovery,
    calculate_portfolio_analysis,
)

TOL = 1e-9


def growth(values, start=(2020, 1, 1)):
    d0 = date(*start)
    return [
        NAVRecord(date=(d0 + timedelta(days=i)).isoformat(), nav=float(v))
        for i, v in enumerate(values)
    ]


def dd(values, start=(2020, 1, 1)):
    return calculate_drawdown_recovery(growth(values, start))


# 1. No drawdown / monotonically rising portfolio.
def test_no_drawdown_monotonic_rising():
    data = dd([100, 101, 102, 103, 104])
    assert data.episodes == []
    assert data.maximum_drawdown == 0.0
    assert data.current_drawdown == 0.0
    assert data.current_status == "At a new high"
    assert data.longest_recovery_days is None


# 2. Single completed drawdown; also covers 5 (recovery exactly at peak),
# 8 (magnitude), 9 (decline duration), 10 (recovery duration).
def test_single_completed_drawdown():
    data = dd([100, 120, 90, 110, 120])
    assert len(data.episodes) == 1
    ep = data.episodes[0]
    assert ep.peak_date == "2020-01-02"
    assert ep.trough_date == "2020-01-03"
    assert ep.recovery_date == "2020-01-05"  # 120 == previous peak 120
    assert ep.drawdown == pytest.approx(90 / 120 - 1, abs=TOL)
    assert ep.decline_duration_days == 1
    assert ep.recovery_duration_days == 2
    assert ep.total_duration_days == 3
    assert ep.is_ongoing is False
    assert data.maximum_drawdown == pytest.approx(-0.25, abs=TOL)
    assert data.longest_recovery_days == 2
    assert data.current_drawdown == pytest.approx(0.0, abs=TOL)
    assert data.current_status == "At a new high"


# 3./11. Single ongoing drawdown.
def test_single_ongoing_drawdown():
    data = dd([100, 120, 90, 95])
    assert len(data.episodes) == 1
    ep = data.episodes[0]
    assert ep.is_ongoing is True
    assert ep.recovery_date is None
    assert ep.recovery_duration_days is None
    assert ep.total_duration_days is None
    assert ep.peak_date == "2020-01-02"
    assert ep.trough_date == "2020-01-03"
    assert ep.decline_duration_days == 1
    assert ep.drawdown == pytest.approx(90 / 120 - 1, abs=TOL)
    assert data.longest_recovery_days is None
    assert data.current_drawdown == pytest.approx(95 / 120 - 1, abs=TOL)
    assert data.current_status == "Still recovering"


# 4. Multiple drawdowns; a lower high below the previous peak stays part of
# the SAME episode (the episode only ends at/above the original peak).
def test_multiple_drawdowns():
    data = dd([100, 110, 95, 105, 100, 120, 108, 120])
    # Episode 1: peak 110, trough 95, recovery at 120 (index 5).
    #   (105 at index 3 is still below 110 -> same episode.)
    # Episode 2: peak 120 (index 5), trough 108, recovery at 120 (index 7).
    assert len(data.episodes) == 2
    e1, e2 = data.episodes[0], data.episodes[1]
    # Sorted most severe first: e1 (-13.6%) deeper than e2 (-10%).
    assert e1.drawdown < e2.drawdown
    assert e1.peak_date == "2020-01-02" and e1.trough_date == "2020-01-03"
    assert e1.recovery_date == "2020-01-06"
    assert e2.peak_date == "2020-01-06" and e2.trough_date == "2020-01-07"
    assert e2.recovery_date == "2020-01-08"
    assert data.maximum_drawdown == pytest.approx(95 / 110 - 1, abs=TOL)
    assert data.longest_recovery_days == 3  # e1: trough (day 2) -> 120 (day 5)


# 5./6. Recovery exactly at the previous peak, and recovery above it.
def test_recovery_at_and_above_previous_peak():
    at_peak = dd([100, 110, 99, 110])
    assert at_peak.episodes[0].recovery_date == "2020-01-04"
    assert at_peak.episodes[0].drawdown == pytest.approx(99 / 110 - 1, abs=TOL)

    above_peak = dd([100, 110, 99, 115])
    assert above_peak.episodes[0].recovery_date == "2020-01-04"
    assert above_peak.episodes[0].drawdown == pytest.approx(99 / 110 - 1, abs=TOL)
    assert above_peak.current_drawdown == pytest.approx(0.0, abs=TOL)
    assert above_peak.current_status == "At a new high"


# 7. New high after recovery becomes the reference peak for later episodes.
def test_new_high_after_recovery():
    data = dd([100, 110, 105, 120, 90, 120])
    assert len(data.episodes) == 2
    deeper = data.episodes[0]  # 90/120 - 1 = -25%, deeper than -4.5%
    assert deeper.peak_date == "2020-01-04"
    assert deeper.trough_date == "2020-01-05"
    assert deeper.drawdown == pytest.approx(90 / 120 - 1, abs=TOL)
    assert deeper.recovery_date == "2020-01-06"
    shallow = [e for e in data.episodes if e.peak_date == "2020-01-02"]
    assert len(shallow) == 1
    assert shallow[0].drawdown == pytest.approx(105 / 110 - 1, abs=TOL)


# 12. Meaningful-episode threshold + top-5 selection.
def test_top5_episode_selection_and_threshold():
    # Dips of 1%, 3%, 5%, 7%, 9%, 11%, 13% below a peak of 100, each fully
    # recovered back to the peak so every dip is its own episode.
    values = [100]
    for d in [0.01, 0.03, 0.05, 0.07, 0.09, 0.11, 0.13]:
        values.append(round(100 * (1 - d), 6))  # trough
        values.append(100)                      # recovery at the same peak
    data = dd(values)
    # The 1% dip is below the 2% meaningful threshold; 6 episodes are
    # meaningful and at most the 5 deepest are displayed.
    assert len(data.episodes) == 5
    magnitudes = [-e.drawdown for e in data.episodes]
    assert magnitudes == sorted(magnitudes, reverse=True)  # most severe first
    assert min(magnitudes) >= 0.05 - 1e-9  # 5 deepest dips (5%..13%)
    assert all(e.recovery_date is not None for e in data.episodes)
    # Summary maximum drawdown still covers ALL episodes (deepest = 13% dip).
    assert data.maximum_drawdown == pytest.approx(-0.13, abs=1e-6)


# 13. Maximum Drawdown reconciliation with the existing portfolio metric.
def test_max_drawdown_reconciles_with_existing_metric():
    # 30 common observations (the engine's minimum) with two clear,
    # completed drawdowns in fund A and a smooth rise in fund B.
    a = [100.0]
    a += [100 + 4 * i for i in range(1, 6)]        # rise to 120 (obs 1-5)
    a += [120 - 10 * i for i in range(1, 4)]       # dip to 90   (obs 6-8)
    a += [90 + 7 * i for i in range(1, 6)]         # rise to 125 (obs 9-13)
    a += [125 - 25 * i for i in range(1, 3)]       # dip to 100  (obs 14-15)
    a += [100 + 3 * (i + 1) for i in range(14)]    # rise to 145 (obs 16-29)
    b = [100 + 1 * i for i in range(30)]           # smooth rise to 129
    assert len(a) == 30 and len(b) == 30

    result = calculate_portfolio_analysis(
        [
            {"scheme_code": "A", "allocation": 50, "navs": growth(a)},
            {"scheme_code": "B", "allocation": 50, "navs": growth(b)},
        ]
    )
    dd_data = result.drawdown_recovery
    assert dd_data is not None
    # The summary covers ALL episodes and reconciles with the existing
    # Maximum Drawdown metric computed on the same growth series.
    assert dd_data.maximum_drawdown == pytest.approx(
        -result.metrics.maximum_drawdown, abs=TOL
    )
    assert min(e.drawdown for e in dd_data.episodes) == pytest.approx(
        dd_data.maximum_drawdown, abs=TOL
    )
    # Two clear episodes, both recovered before the end (last obs is a high).
    assert len(dd_data.episodes) == 2
    assert all(not e.is_ongoing for e in dd_data.episodes)
    assert dd_data.current_drawdown == pytest.approx(0.0, abs=TOL)
    assert dd_data.current_status == "At a new high"


# 14. Empty/insufficient series handling.
def test_empty_and_insufficient_series():
    assert calculate_drawdown_recovery([]) is None
    assert calculate_drawdown_recovery(growth([100])) is None


# Flat series: zero drawdown everywhere, no fabricated status.
def test_flat_series():
    data = dd([100, 100, 100, 100])
    assert data.episodes == []
    assert data.maximum_drawdown == 0.0
    assert data.current_drawdown == 0.0
    assert data.current_status == "At a new high"
    assert data.longest_recovery_days is None
