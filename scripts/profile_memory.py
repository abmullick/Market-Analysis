"""Detailed memory profiling for TigZig ranking pipeline."""
import asyncio
import sys
import gc

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


def get_rss_mb():
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def profile_pipeline():
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings
    from backend.services.mutual_funds.lookback import get_required_lookback_years, get_date_range_for_lookback
    from backend.services.data.tigzig import get_tigzig_dataset
    from backend.services.data.tigzig import get_tigzig_metadata

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)
    dataset = get_tigzig_dataset()

    print("=" * 80)
    print("MEMORY PROFILING: TigZig Ranking Pipeline")
    print("=" * 80)

    # Test with Debt - Corporate Bond (22 funds)
    category = "Debt - Corporate Bond"
    underlying_funds = await fetcher.get_ranking_candidates_by_category(category)
    print(f"\nCategory: {category}")
    print(f"Number of funds: {len(underlying_funds)}")

    criteria_names = ["1Y_return", "sharpe_ratio"]
    lookback_years = get_required_lookback_years(criteria_names)
    start_date, end_date = get_date_range_for_lookback(lookback_years)
    print(f"Criteria: {criteria_names}")
    print(f"Lookback: {lookback_years} years")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Force garbage collection before profiling
    gc.collect()

    # STAGE 0: Baseline
    print("\n" + "-" * 60)
    print("STAGE 0: Baseline (before batch processing)")
    print("-" * 60)
    mem_baseline = get_rss_mb()
    print(f"RSS Memory: {mem_baseline:.1f} MB")

    # STAGE 1: Before Parquet query
    print("\n" + "-" * 60)
    print("STAGE 1: Before Parquet query")
    print("-" * 60)
    mem_before_query = get_rss_mb()
    print(f"RSS Memory: {mem_before_query:.1f} MB")

    # STAGE 2: After PyArrow query
    print("\n" + "-" * 60)
    print("STAGE 2: After PyArrow query (before conversion)")
    print("-" * 60)

    # Query TigZig for all funds at once
    all_codes = [int(fund["_representative_scheme_code"]) for fund in underlying_funds]
    print(f"Querying {len(all_codes)} schemes...")

    nav_data = dataset.query_nav(
        all_codes,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
    )

    mem_after_query = get_rss_mb()
    total_rows = sum(len(v) for v in nav_data.values())
    print(f"RSS Memory: {mem_after_query:.1f} MB")
    print(f"Memory increase from query: {mem_after_query - mem_before_query:.1f} MB")
    print(f"Total NAV rows returned: {total_rows:,}")
    print(f"Type of nav_data: {type(nav_data)}")
    print(f"Number of schemes with data: {len([v for v in nav_data.values() if v])}")

    # Check the structure of nav_data
    sample_code = all_codes[0]
    sample_nav = nav_data.get(sample_code, [])
    if sample_nav:
        print(f"\nSample NAV record structure:")
        print(f"  Type: {type(sample_nav[0])}")
        print(f"  Content: {sample_nav[0]}")

    # STAGE 3: After Arrow → Python conversion (this happens inside query_nav)
    print("\n" + "-" * 60)
    print("STAGE 3: After Arrow → Python dict conversion")
    print("-" * 60)
    mem_after_conversion = get_rss_mb()
    print(f"RSS Memory: {mem_after_conversion:.1f} MB")
    print(f"Memory increase from conversion: {mem_after_conversion - mem_after_query:.1f} MB")

    # STAGE 4: After grouping data by scheme (already done in query_nav)
    print("\n" + "-" * 60)
    print("STAGE 4: After grouping by scheme")
    print("-" * 60)
    mem_after_grouping = get_rss_mb()
    print(f"RSS Memory: {mem_after_grouping:.1f} MB")

    # STAGE 5: After metric calculation
    print("\n" + "-" * 60)
    print("STAGE 5: After metric calculation (batch)")
    print("-" * 60)

    # Now run the actual batch processing
    gc.collect()
    mem_before_batch = get_rss_mb()
    print(f"RSS Memory before batch: {mem_before_batch:.1f} MB")

    # Re-query to simulate actual batch processing
    metrics_list = await fetcher.get_metrics_batch(underlying_funds, criteria_names)

    mem_after_batch = get_rss_mb()
    successful = sum(1 for m in metrics_list if m is not None)
    print(f"RSS Memory after batch: {mem_after_batch:.1f} MB")
    print(f"Memory increase from batch: {mem_after_batch - mem_before_batch:.1f} MB")
    print(f"Successful calculations: {successful}/{len(underlying_funds)}")

    # STAGE 6: After metric objects stored in cache
    print("\n" + "-" * 60)
    print("STAGE 6: After metrics stored in cache")
    print("-" * 60)
    mem_after_cache = get_rss_mb()
    print(f"RSS Memory: {mem_after_cache:.1f} MB")

    # Check what's in the cache
    from backend.services.mutual_funds.cache import metrics_cache
    cache_stats = metrics_cache.stats()
    print(f"Cache stats: {cache_stats}")

    # STAGE 7: After explicit release of temporary objects
    print("\n" + "-" * 60)
    print("STAGE 7: After releasing temporary objects")
    print("-" * 60)
    del nav_data
    del metrics_list
    gc.collect()
    mem_after_release = get_rss_mb()
    print(f"RSS Memory: {mem_after_release:.1f} MB")
    print(f"Memory after release: {mem_after_release - mem_after_batch:.1f} MB")

    # STAGE 8: After TigZig metadata loading
    print("\n" + "-" * 60)
    print("STAGE 8: After TigZig metadata loading")
    print("-" * 60)
    mem_before_metadata = get_rss_mb()
    metadata_service = get_tigzig_metadata()
    metadata = await metadata_service.get_metadata()
    mem_after_metadata = get_rss_mb()
    print(f"RSS Memory: {mem_after_metadata:.1f} MB")
    print(f"Memory increase from metadata: {mem_after_metadata - mem_before_metadata:.1f} MB")
    print(f"Number of metadata entries: {len(metadata)}")

    # SUMMARY
    print("\n" + "=" * 80)
    print("MEMORY PROFILING SUMMARY")
    print("=" * 80)
    print(f"{'Stage':<40} {'Memory (MB)':<15} {'Delta (MB)':<15}")
    print("-" * 70)
    print(f"{'0. Baseline':<40} {mem_baseline:<15.1f} {'-':<15}")
    print(f"{'1. Before Parquet query':<40} {mem_before_query:<15.1f} {mem_before_query - mem_baseline:<15.1f}")
    print(f"{'2. After PyArrow query':<40} {mem_after_query:<15.1f} {mem_after_query - mem_before_query:<15.1f}")
    print(f"{'3. After Arrow→Python conversion':<40} {mem_after_conversion:<15.1f} {mem_after_conversion - mem_after_query:<15.1f}")
    print(f"{'4. After grouping':<40} {mem_after_grouping:<15.1f} {mem_after_grouping - mem_after_conversion:<15.1f}")
    print(f"{'5. After metric calculation':<40} {mem_after_batch:<15.1f} {mem_after_batch - mem_before_batch:<15.1f}")
    print(f"{'6. After cache storage':<40} {mem_after_cache:<15.1f} {mem_after_cache - mem_after_batch:<15.1f}")
    print(f"{'7. After releasing temp objects':<40} {mem_after_release:<15.1f} {mem_after_release - mem_after_cache:<15.1f}")
    print(f"{'8. After metadata loading':<40} {mem_after_metadata:<15.1f} {mem_after_metadata - mem_after_release:<15.1f}")
    print("-" * 70)
    print(f"{'TOTAL INCREASE':<40} {mem_after_metadata - mem_baseline:<15.1f}")


if __name__ == "__main__":
    asyncio.run(profile_pipeline())
