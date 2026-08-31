"""Benchmark comparing OLD vs NEW calculator implementation.

Measures for 10, 50, 100, 500, 1000 funds:
- metric calculation time (old vs new)
- _rolling_consistency time (old vs new)
- total ranking time
- peak RSS
- number of funds successfully ranked
"""
import sys
import time
import resource

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

from backend.models.mutual_fund import NAVRecord


def get_rss_mb():
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) / 1024
    except Exception:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _make_navs(values, start_date, days_between=1):
    base = datetime.strptime(start_date, "%Y-%m-%d")
    return [
        NAVRecord(date=(base + timedelta(days=i * days_between)).strftime("%Y-%m-%d"), nav=v)
        for i, v in enumerate(values)
    ]


def make_realistic_fund(num_days=365 * 5, start_date="2019-01-01", seed=None):
    import random
    if seed is None:
        seed = hash(start_date) % 2**32
    random.seed(seed)
    nav = 100.0
    values = [nav]
    for i in range(1, num_days):
        change = random.gauss(0.0005, 0.015)
        nav *= (1 + change)
        nav = max(nav, 0.01)
        values.append(nav)
    return _make_navs(values, start_date)


def load_calculator(module_name):
    """Load a calculator module by name."""
    if module_name == "new":
        from backend.services.mutual_funds.calculator import MetricsCalculator
    else:
        from backend.services.mutual_funds.calculator_reference import MetricsCalculator
    return MetricsCalculator


def compare_metrics(old_result, new_result):
    """Compare two FundMetrics for exact equality."""
    if old_result is None and new_result is None:
        return True
    if old_result is None or new_result is None:
        return False
    
    fields = [
        "one_year_return", "three_year_cagr", "five_year_cagr", "ten_year_cagr",
        "annualized_volatility", "sharpe_ratio", "sortino_ratio",
        "maximum_drawdown", "downside_deviation",
    ]
    
    for field in fields:
        old_val = getattr(old_result, field)
        new_val = getattr(new_result, field)
        if old_val is None and new_val is None:
            continue
        if old_val is None or new_val is None:
            return False
        if abs(old_val - new_val) > 1e-10:
            return False
    
    # Compare rolling consistency
    old_rc = old_result.rolling_return_consistency
    new_rc = new_result.rolling_return_consistency
    if old_rc is None and new_rc is None:
        return True
    if old_rc is None or new_rc is None:
        return False
    
    for period in ["1Y", "3Y", "5Y"]:
        old_p = old_rc.get(period)
        new_p = new_rc.get(period)
        if old_p is None and new_p is None:
            continue
        if old_p is None or new_p is None:
            return False
        for key in ["windows", "positive_pct", "mean_return", "std_return"]:
            old_v = old_p.get(key)
            new_v = new_p.get(key)
            if old_v is None and new_v is None:
                continue
            if old_v is None or new_v is None:
                return False
            if key == "std_return":
                if old_v is None and new_v is None:
                    continue
                if old_v is None or new_v is None:
                    return False
                if abs(old_v - new_v) > 1e-10:
                    return False
            else:
                if abs(old_v - new_v) > 1e-10:
                    return False
    
    return True


def correctness_verification():
    """Verify old and new produce identical results for various test cases."""
    print("=" * 80)
    print("CORRECTNESS VERIFICATION")
    print("=" * 80)
    
    MetricsCalculatorOld = load_calculator("old")
    MetricsCalculatorNew = load_calculator("new")
    
    test_cases = [
        ("Small fund (2 NAVs)", _make_navs([100.0, 110.0], "2024-01-01")),
        ("Medium fund (366 NAVs)", _make_navs([100.0 + i for i in range(366)], "2023-01-01")),
        ("3Y fund (1100 NAVs)", _make_navs([100.0] * 1100, "2020-01-01")),
        ("Volatile fund", _make_navs([100.0, 110.0, 90.0, 120.0, 80.0], "2024-01-01")),
        ("Zero start NAV", _make_navs([0.0, 110.0], "2024-01-01")),
        ("Gap in data", [
            NAVRecord(date="2023-01-01", nav=100.0),
            NAVRecord(date="2023-01-02", nav=101.0),
            NAVRecord(date="2023-01-10", nav=110.0),
            NAVRecord(date="2023-01-11", nav=111.0),
        ]),
    ]
    
    all_pass = True
    for name, navs in test_cases:
        old_calc = MetricsCalculatorOld(scheme_code="TEST", nav_records=list(navs))
        new_calc = MetricsCalculatorNew(scheme_code="TEST", nav_records=list(navs))
        
        old_result = old_calc.calculate()
        new_result = new_calc.calculate()
        
        match = compare_metrics(old_result, new_result)
        status = "PASS" if match else "FAIL"
        if not match:
            all_pass = False
        
        print(f"  {name}: {status}")
        if not match:
            print(f"    OLD: {old_result}")
            print(f"    NEW: {new_result}")
    
    # Test with large realistic fund
    print("\n  Large realistic fund (1825 NAVs):")
    navs = make_realistic_fund(num_days=1825, seed=12345)
    old_calc = MetricsCalculatorOld(scheme_code="TEST", nav_records=list(navs))
    new_calc = MetricsCalculatorNew(scheme_code="TEST", nav_records=list(navs))
    old_result = old_calc.calculate()
    new_result = new_calc.calculate()
    match = compare_metrics(old_result, new_result)
    status = "PASS" if match else "FAIL"
    if not match:
        all_pass = False
    print(f"    {status}")
    
    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


def benchmark_impl(impl_name, num_funds, iterations=1):
    """Benchmark a specific implementation."""
    MetricsCalculator = load_calculator(impl_name)
    
    times = []
    rss_vals = []
    successes = []
    
    for iter_idx in range(iterations):
        funds_data = []
        for i in range(num_funds):
            seed = (iter_idx * 10000 + i) % 2**32
            navs = make_realistic_fund(seed=seed)
            funds_data.append((f"TEST{i}_{iter_idx}", navs))
        
        rss_before = get_rss_mb()
        t0 = time.perf_counter()
        
        successful = 0
        for scheme_code, navs in funds_data:
            try:
                calc = MetricsCalculator(scheme_code=scheme_code, nav_records=list(navs))
                metrics = calc.calculate()
                if metrics is not None:
                    successful += 1
            except Exception as e:
                pass
        
        t1 = time.perf_counter()
        rss_after = get_rss_mb()
        
        elapsed = t1 - t0
        times.append(elapsed)
        rss_vals.append(rss_after)
        successes.append(successful)
    
    return {
        "avg_elapsed": sum(times) / len(times),
        "min_elapsed": min(times),
        "max_elapsed": max(times),
        "avg_rss": sum(rss_vals) / len(rss_vals),
        "avg_success": sum(successes) / len(successes),
    }


def benchmark_fund_count(num_funds, iterations=2):
    """Benchmark old vs new for a given number of funds."""
    print(f"\n{'='*80}")
    print(f"BENCHMARK: {num_funds} funds ({iterations} iterations)")
    print(f"{'='*80}")
    
    results = {}
    for impl in ["old", "new"]:
        results[impl] = benchmark_impl(impl, num_funds, iterations)
    
    for impl in ["old", "new"]:
        r = results[impl]
        print(f"  {impl.upper()}:")
        print(f"    Total time:        {r['avg_elapsed']:.3f}s")
        print(f"    Per fund:          {r['avg_elapsed']/num_funds*1000:.2f}ms")
        print(f"    Peak RSS:         {r['avg_rss']:.1f} MB")
        print(f"    Successful:       {r['avg_success']:.0f}/{num_funds}")
    
    old_time = results["old"]["avg_elapsed"]
    new_time = results["new"]["avg_elapsed"]
    speedup = old_time / new_time if new_time > 0 else float("inf")
    print(f"\n  SPEEDUP: {speedup:.2f}x")
    
    return results


if __name__ == "__main__":
    correctness_verification()
    
    for num_funds in [10, 50, 100, 500, 1000]:
        benchmark_fund_count(num_funds, iterations=2)
