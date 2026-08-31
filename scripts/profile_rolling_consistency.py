"""Profile _rolling_consistency precisely to measure its contribution.

Measures:
- Time spent in _rolling_consistency specifically
- Time spent in _rolling_returns (called 3x from _rolling_consistency)
- Total metric calculation time
"""
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

from backend.models.mutual_fund import NAVRecord
from backend.services.mutual_funds.calculator import MetricsCalculator


def _make_navs(values, start_date, days_between=1):
    base = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        NAVRecord(date=(base + timedelta(days=i * days_between)).strftime("%Y-%m-%d"), nav=v)
        for i, v in enumerate(values)
    ]


def make_realistic_fund(num_days=365 * 5, start_date="2019-01-01"):
    """Generate a realistic NAV series with ~5 years of daily data."""
    import random
    random.seed(42)
    nav = 100.0
    values = [nav]
    for i in range(1, num_days):
        change = random.gauss(0.0005, 0.015)
        nav *= (1 + change)
        nav = max(nav, 0.01)
        values.append(nav)
    return _make_navs(values, start_date)


def profile_rolling_returns_calls():
    """Profile _rolling_returns individually to see why 3 calls are expensive."""
    print("=" * 80)
    print("PROFILING _rolling_returns calls")
    print("=" * 80)
    
    navs = make_realistic_fund(num_days=365 * 5)
    calc = MetricsCalculator(scheme_code="TEST", nav_records=list(navs))
    
    windows = {"1Y": 365, "3Y": 1095, "5Y": 1825}
    
    for label, days in windows.items():
        t0 = time.perf_counter()
        returns = calc._rolling_returns(navs, days)
        t1 = time.perf_counter()
        print(f"  _rolling_returns({label}, {days} days): {len(returns)} windows in {(t1-t0)*1000:.2f}ms")
        print(f"    date parsing: ~{len(navs)} strptime calls per call")


def profile_calculate_components():
    """Profile each component of calculate()."""
    print("\n" + "=" * 80)
    print("PROFILING calculate() components")
    print("=" * 80)
    
    navs = make_realistic_fund(num_days=365 * 5)
    calc = MetricsCalculator(scheme_code="TEST", nav_records=list(navs))
    
    # Time individual components
    t0 = time.perf_counter()
    rc = calc._rolling_consistency(navs)
    t_rc = time.perf_counter() - t0
    
    t0 = time.perf_counter()
    metrics = calc.calculate()
    t_calc = time.perf_counter() - t0
    
    print(f"  _rolling_consistency alone: {t_rc*1000:.2f}ms")
    print(f"  Full calculate():          {t_calc*1000:.2f}ms")
    print(f"  _rolling_consistency %:     {(t_rc/t_calc)*100:.1f}%")
    
    return t_rc, t_calc


def profile_by_fund_count():
    """Profile for different numbers of funds - only _rolling_consistency + calculate."""
    print("\n" + "=" * 80)
    print("PROFILING by fund count")
    print("=" * 80)
    
    for num_funds in [10, 50, 100, 500]:
        print(f"\n--- {num_funds} funds ---")
        
        total_rc_time = 0
        total_calc_time = 0
        
        for i in range(num_funds):
            navs = make_realistic_fund()
            calc = MetricsCalculator(scheme_code=f"TEST{i}", nav_records=navs)
            
            t0 = time.perf_counter()
            rc = calc._rolling_consistency(navs)
            t1 = time.perf_counter()
            total_rc_time += (t1 - t0)
            
            t0 = time.perf_counter()
            metrics = calc.calculate()
            t1 = time.perf_counter()
            total_calc_time += (t1 - t0)
        
        avg_rc = total_rc_time / num_funds
        avg_calc = total_calc_time / num_funds
        pct = (total_rc_time / total_calc_time) * 100 if total_calc_time > 0 else 0
        
        print(f"  Avg _rolling_consistency: {avg_rc*1000:.2f}ms")
        print(f"  Avg total calculate:      {avg_calc*1000:.2f}ms")
        print(f"  _rolling_consistency %:   {pct:.1f}%")


if __name__ == "__main__":
    profile_rolling_returns_calls()
    profile_calculate_components()
    profile_by_fund_count()
