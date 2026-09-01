"""Extended diagnostic: trace metric calculation stage."""
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


async def diagnose_metrics_calculation():
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings
    from backend.services.mutual_funds.lookback import get_required_lookback_years, get_date_range_for_lookback
    from backend.services.data.tigzig import get_tigzig_dataset
    from backend.services.mutual_funds.calculator import MetricsCalculator
    from backend.models.mutual_fund import NAVRecord

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)
    dataset = get_tigzig_dataset()

    print("=" * 80)
    print("STEP 4: Metric calculation trace")
    print("=" * 80)

    category = "Debt - Corporate Bond"
    underlying_funds = await fetcher.get_ranking_candidates_by_category(category)

    # Test with first fund
    fund = underlying_funds[0]
    rep_code = int(fund["_representative_scheme_code"])
    fund_name = fund.get("_canonical_fund_name", "Unknown")

    # Criteria that would typically be used
    criteria_names = ["1Y_return", "sharpe_ratio"]
    lookback_years = get_required_lookback_years(criteria_names)
    start_date, end_date = get_date_range_for_lookback(lookback_years)

    print(f"\nFund: {fund_name}")
    print(f"Code: {rep_code}")
    print(f"Criteria: {criteria_names}")
    print(f"Lookback: {lookback_years} years")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Get NAV data
    nav_data = dataset.query_nav(
        [rep_code],
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )
    fund_nav = nav_data.get(rep_code, [])

    print(f"\nNAV rows returned: {len(fund_nav)}")
    if fund_nav:
        print(f"First: {fund_nav[0]}")
        print(f"Last: {fund_nav[-1]}")

    # Convert to NAVRecord
    nav_records = [NAVRecord(date=d["date"], nav=d["nav"]) for d in fund_nav]
    print(f"\nNAVRecord count: {len(nav_records)}")

    # Calculate metrics
    print("\n--- Calculating metrics ---")
    calculator = MetricsCalculator(scheme_code=str(rep_code), nav_records=nav_records)
    metrics = calculator.calculate()

    print(f"\nMetrics calculated:")
    print(f"  scheme_code: {metrics.scheme_code}")
    print(f"  data_start_date: {metrics.data_start_date}")
    print(f"  data_end_date: {metrics.data_end_date}")
    print(f"  data_points: {metrics.data_points}")
    print(f"  years_available: {metrics.years_available}")
    print(f"  one_year_return: {metrics.one_year_return}")
    print(f"  three_year_cagr: {metrics.three_year_cagr}")
    print(f"  five_year_cagr: {metrics.five_year_cagr}")
    print(f"  ten_year_cagr: {metrics.ten_year_cagr}")
    print(f"  annualized_volatility: {metrics.annualized_volatility}")
    print(f"  sharpe_ratio: {metrics.sharpe_ratio}")
    print(f"  sortino_ratio: {metrics.sortino_ratio}")
    print(f"  maximum_drawdown: {metrics.maximum_drawdown}")
    print(f"  downside_deviation: {metrics.downside_deviation}")
    print(f"  rolling_return_consistency: {metrics.rolling_return_consistency}")

    # Check which metrics are None
    print("\n--- Checking for None values ---")
    none_fields = []
    for field in ["one_year_return", "three_year_cagr", "five_year_cagr", "ten_year_cagr",
                  "annualized_volatility", "sharpe_ratio", "sortino_ratio",
                  "maximum_drawdown", "downside_deviation", "rolling_return_consistency"]:
        value = getattr(metrics, field)
        if value is None:
            none_fields.append(field)
            print(f"  {field}: None")

    if none_fields:
        print(f"\n  WARNING: {len(none_fields)} metrics are None!")
    else:
        print(f"\n  All metrics have values")

    # Now test the actual batch processing
    print("\n" + "=" * 80)
    print("STEP 5: Test actual batch processing")
    print("=" * 80)

    # Test with all 22 funds
    test_funds = underlying_funds[:5]  # First 5 for now
    print(f"\nTesting batch processing with {len(test_funds)} funds...")

    metrics_list = await fetcher.get_metrics_batch(test_funds, criteria_names)

    print(f"\nResults:")
    for i, (fund, metrics) in enumerate(zip(test_funds, metrics_list)):
        code = fund.get("_representative_scheme_code")
        name = fund.get("_canonical_fund_name", "Unknown")
        if metrics is None:
            print(f"  {i+1}. {name} ({code}): FAILED - metrics is None")
        else:
            print(f"  {i+1}. {name} ({code}): OK - sharpe={metrics.get('sharpe_ratio')}, return={metrics.get('one_year_return')}")


if __name__ == "__main__":
    asyncio.run(diagnose_metrics_calculation())
