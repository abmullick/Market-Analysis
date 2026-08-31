"""Documentation of _rolling_consistency current behavior.

== CURRENT BEHAVIOR OF _rolling_consistency ==

1. PERIODS/WINDOWS CALCULATED:
   - 1Y: 365-day rolling windows
   - 3Y: 1095-day rolling windows (3 * 365)
   - 5Y: 1825-day rolling windows (5 * 365)

2. HOW OBSERVATIONS ARE SELECTED:
   - NAV records are sorted by date in __init__ (already done)
   - For each end date position i (from 1 to len(navs)-1):
     * target_start = date[i] - window_days
     * Find the earliest start_idx such that date[start_idx] <= target_start
     * The search uses a sliding start_idx that only moves forward
     * Only returns where start_nav > 0 are included

3. HOW RETURNS ARE CALCULATED:
   - return = nav[i] / nav[start_idx] - 1
   - This is a simple (non-log) return over the window

4. HOW MISSING OBSERVATIONS ARE HANDLED:
   - Gaps in dates are handled naturally: the sliding start_idx advances
     based on actual dates, not index positions
   - If no valid start point exists for a window, that observation is skipped
   - If a fund has insufficient history (fewer than 2 NAVs), returns None

5. HOW THE FINAL CONSISTENCY PERCENTAGE IS PRODUCED:
   - For each window (1Y, 3Y, 5Y):
     * windows: count of valid rolling returns
     * positive_pct: percentage of returns > 0
     * mean_return: arithmetic mean of all window returns
     * std_return: sample standard deviation of window returns (N-1 denominator)
   - If no window has data, returns None
   - If at least one window has data, returns the dict with available periods

== WHY IT IS CALLED 3 TIMES ==

_rolling_consistency calls _rolling_returns three times, once for each
window size (365, 1095, 1825 days). Each call:
  1. Parses ALL NAV dates with datetime.strptime (~1825 calls)
  2. Iterates through ALL NAV records with a sliding window
  3. Builds a separate list of returns

Total work per fund: 3 full passes over NAV data, 3 * N strptime calls.

== CAN THE THREE CALCULATIONS SHARE INTERMEDIATE DATA? ==

YES. All three windows operate on the same NAV data with the same
loop structure. The only difference is the window_days parameter.

Optimization: Parse dates ONCE, then in a single loop over navs,
maintain three separate start_idx values (one per window) and compute
all three return lists simultaneously.

Expected speedup: ~2/3 reduction in _rolling_consistency time
(because we go from 3 passes to 1 pass, and 3*N strptime to N strptime).

== OTHER LOW-RISK OPTIMIZATIONS ==

1. Pre-parse dates in calculate() to avoid repeated strptime in:
   - _slice_navs (called 4 times, linear scan with strptime per record)
   - _cagr (called 3 times, strptime on first/last record)
   - _rolling_consistency (already optimized above)

2. Use binary search (bisect) in _slice_navs instead of linear scan

3. Cache parsed_dates as a local variable in calculate()
"""
