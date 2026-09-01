"""Diagnostic script to trace Corporate Bond schemes through ranking pipeline."""
import asyncio
import sys
from datetime import datetime

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


async def diagnose_corporate_bond():
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings
    from backend.services.mutual_funds.lookback import get_required_lookback_years, get_date_range_for_lookback
    from backend.services.data.tigzig import get_tigzig_dataset

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)
    dataset = get_tigzig_dataset()

    print("=" * 80)
    print("STEP 1: Category filtering")
    print("=" * 80)

    category = "Debt - Corporate Bond"
    underlying_funds = await fetcher.get_ranking_candidates_by_category(category)
    print(f"Found {len(underlying_funds)} underlying funds in category: {category}")

    if not underlying_funds:
        print("No funds found!")
        return

    # Select first 3 funds for detailed tracing
    test_funds = underlying_funds[:3]
    print(f"\nTracing {len(test_funds)} representative funds:")

    # Criteria that would typically be used
    criteria_names = ["1Y_return", "sharpe_ratio"]
    lookback_years = get_required_lookback_years(criteria_names)
    start_date, end_date = get_date_range_for_lookback(lookback_years)

    print(f"\nCriteria: {criteria_names}")
    print(f"Lookback years: {lookback_years}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    for i, fund in enumerate(test_funds):
        print("\n" + "=" * 80)
        print(f"FUND {i+1}: {fund.get('_canonical_fund_name', 'Unknown')}")
        print("=" * 80)

        # STEP 2: Scheme code extraction
        print("\n--- STEP 2: Scheme code extraction ---")
        rep_code = fund.get("_representative_scheme_code")
        print(f"  _representative_scheme_code: {rep_code} (type: {type(rep_code).__name__})")
        print(f"  scheme_code: {fund.get('scheme_code')} (type: {type(fund.get('scheme_code')).__name__})")
        print(f"  scheme_name: {fund.get('scheme_name')}")
        print(f"  _canonical_fund_name: {fund.get('_canonical_fund_name')}")
        print(f"  category: {fund.get('category')}")
        print(f"  _canonical_category: {fund.get('_canonical_category')}")

        code_int = int(rep_code)

        # STEP 3: TigZig Parquet lookup
        print("\n--- STEP 3: TigZig Parquet lookup ---")
        print(f"  Dataset available: {dataset.is_available}")
        print(f"  Querying for scheme_code: {code_int}")
        print(f"  Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        try:
            nav_data = dataset.query_nav(
                [code_int],
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )
            print(f"  NAV data returned: {nav_data}")

            fund_nav = nav_data.get(code_int, [])
            print(f"  Number of NAV rows: {len(fund_nav)}")

            if fund_nav:
                print(f"  First NAV record: {fund_nav[0]}")
                print(f"  Last NAV record: {fund_nav[-1]}")

                # Check for valid NAV values
                valid_navs = [n for n in fund_nav if n.get("nav") is not None and n.get("nav") > 0]
                print(f"  Valid NAV observations (nav > 0): {len(valid_navs)}")

                # Check date format
                sample_dates = [n.get("date") for n in fund_nav[:5]]
                print(f"  Sample dates: {sample_dates}")
                print(f"  Date type: {type(fund_nav[0].get('date')).__name__}")
            else:
                print("  NO NAV DATA RETURNED!")

                # Try without date filter
                print("\n  Trying without date filter...")
                nav_data_no_filter = dataset.query_nav([code_int])
                fund_nav_no_filter = nav_data_no_filter.get(code_int, [])
                print(f"  NAV rows without date filter: {len(fund_nav_no_filter)}")
                if fund_nav_no_filter:
                    print(f"  First record: {fund_nav_no_filter[0]}")
                    print(f"  Last record: {fund_nav_no_filter[-1]}")

        except Exception as e:
            print(f"  ERROR querying TigZig: {e}")
            import traceback
            traceback.print_exc()

    # Also test a known equity fund for comparison
    print("\n" + "=" * 80)
    print("COMPARISON: Testing equity fund")
    print("=" * 80)

    equity_category = "Large Cap"
    equity_funds = await fetcher.get_ranking_candidates_by_category(equity_category)
    print(f"Found {len(equity_funds)} equity funds in category: {equity_category}")

    if equity_funds:
        equity_fund = equity_funds[0]
        eq_code = int(equity_fund.get("_representative_scheme_code"))
        print(f"Testing equity fund: {equity_fund.get('_canonical_fund_name')} (code: {eq_code})")

        try:
            nav_data = dataset.query_nav(
                [eq_code],
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )
            fund_nav = nav_data.get(eq_code, [])
            print(f"  NAV rows returned: {len(fund_nav)}")
            if fund_nav:
                print(f"  First: {fund_nav[0]}")
                print(f"  Last: {fund_nav[-1]}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(diagnose_corporate_bond())
