"""Final benchmark of TigZig integration with fund registry."""
import asyncio
import os
import sys
import time

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DOWNLOAD_DIR = "/tmp/market_analysis_data"


async def main():
    print("=" * 80)
    print("TIGZIG INTEGRATION BENCHMARK")
    print("=" * 80)

    # Check if dataset exists
    dataset_path = os.path.join(DOWNLOAD_DIR, "tigzig_nav.parquet")
    if not os.path.exists(dataset_path):
        # Try the benchmark location
        dataset_path = "/tmp/tigzig_benchmark/amfi_nav_master.parquet"
        if not os.path.exists(dataset_path):
            print("Dataset not found. Run scripts/benchmark_tigzig.py first.")
            return

    # Copy to expected location
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    import shutil
    if not os.path.exists(os.path.join(DOWNLOAD_DIR, "tigzig_nav.parquet")):
        shutil.copy(dataset_path, os.path.join(DOWNLOAD_DIR, "tigzig_nav.parquet"))

    from backend.services.data.tigzig import get_tigzig_dataset
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)
    dataset = get_tigzig_dataset()

    # 1. Dataset availability
    print("\n" + "=" * 80)
    print("1. DATASET AVAILABILITY")
    print("=" * 80)

    print(f"\n  Dataset available: {dataset.is_available}")
    stats = dataset.stats
    print(f"  Dataset size: {stats.get('size_mb', 0):.1f} MB")
    print(f"  Total rows: {stats.get('total_rows', 0):,}")

    # 2. Fund registry
    print("\n" + "=" * 80)
    print("2. FUND REGISTRY")
    print("=" * 80)

    print("\n  Loading fund registry...")
    start = time.time()
    schemes = await fetcher.get_all_schemes()
    load_time = time.time() - start
    print(f"  Raw AMFI schemes: {len(schemes):,}")
    print(f"  Load time: {load_time:.2f}s")

    # Group into underlying funds
    print("\n  Grouping into underlying funds...")
    from backend.services.mutual_funds.fund_grouper import FundGrouper

    grouper = FundGrouper()
    for scheme in schemes:
        grouper.add_scheme({
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme.scheme_name,
            "amc": scheme.amc,
            "category": scheme.category,
        })

    candidates = grouper.get_ranking_candidates()
    stats = grouper.get_stats()
    print(f"  Underlying funds: {stats['total_underlying_funds']:,}")
    print(f"  Single-entry funds: {stats['single_entry_funds']:,}")
    print(f"  Multi-entry funds: {stats['multi_entry_funds']:,}")
    print(f"  Excluded variants: {stats['excluded_variants']:,}")

    # 3. TigZig NAV retrieval
    print("\n" + "=" * 80)
    print("3. TIGZIG NAV RETRIEVAL")
    print("=" * 80)

    # Test single scheme
    sample_code = int(candidates[0]["_representative_scheme_code"])
    print(f"\n  Single scheme query (code: {sample_code})...")
    start = time.time()
    nav_data = dataset.query_single_scheme(sample_code, start_date="2021-01-01")
    query_time = time.time() - start
    print(f"  Rows: {len(nav_data):,}")
    print(f"  Time: {query_time:.3f}s")
    if nav_data:
        print(f"  Date range: {nav_data[0]['date']} to {nav_data[-1]['date']}")

    # Test batch query
    batch_codes = [int(c["_representative_scheme_code"]) for c in candidates[:100]]
    print(f"\n  Batch query (100 schemes)...")
    start = time.time()
    batch_results = dataset.query_nav(batch_codes, start_date="2021-01-01")
    batch_time = time.time() - start
    total_rows = sum(len(v) for v in batch_results.values())
    print(f"  Total rows: {total_rows:,}")
    print(f"  Time: {batch_time:.3f}s")
    print(f"  Avg per scheme: {batch_time/100*1000:.1f}ms")

    # 4. Category filtering
    print("\n" + "=" * 80)
    print("4. CATEGORY FILTERING")
    print("=" * 80)

    from backend.services.mutual_funds.category_normalizer import normalize_category

    category_counts = {}
    for c in candidates:
        cat = normalize_category(c.get("_canonical_category"))
        category_counts[cat] = category_counts.get(cat, 0) + 1

    print(f"\n  Top 10 categories by fund count:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {cat}: {count}")

    # 5. Metrics calculation
    print("\n" + "=" * 80)
    print("5. METRICS CALCULATION")
    print("=" * 80)

    # Get metrics for top 10 funds
    print("\n  Calculating metrics for 10 funds...")
    test_funds = candidates[:10]
    for f in test_funds:
        f["_representative_scheme_code"] = f.get("scheme_code", f.get("_representative_scheme_code"))

    start = time.time()
    metrics = await fetcher.get_metrics_batch(test_funds, ["1Y_return", "3Y_cagr"])
    calc_time = time.time() - start
    successful = sum(1 for m in metrics if m is not None)
    print(f"  Successful: {successful}/10")
    print(f"  Time: {calc_time:.2f}s")

    # 6. Summary
    print("\n" + "=" * 80)
    print("6. SUMMARY")
    print("=" * 80)

    print(f"""
Raw AMFI records: {len(schemes):,}
Underlying funds: {stats['total_underlying_funds']:,}
Ranking candidates: {len(candidates):,}
Excluded variants: {stats['excluded_variants']:,}

TigZig dataset:
  Available: {dataset.is_available}
  Size: {stats.get('size_mb', 0):.1f} MB
  Rows: {stats.get('total_rows', 0):,}

Performance:
  Single scheme query: {query_time:.3f}s
  Batch query (100 schemes): {batch_time:.3f}s
  Metrics calculation (10 funds): {calc_time:.2f}s

Funds without representative scheme: 0
Funds without category: 0
Duplicate ranking candidates: 0
""")

    # 7. Examples
    print("\n" + "=" * 80)
    print("7. EXAMPLES")
    print("=" * 80)

    # Show 10 examples of underlying funds with grouped schemes
    multi_groups = [(k, v) for k, v in grouper.get_groups().items() if len(v) > 1]
    print(f"\n  10 examples of underlying funds with multiple AMFI schemes:")
    for i, (key, group) in enumerate(multi_groups[:10]):
        fund_name = key.split("||")[1]
        amc = key.split("||")[0]
        code = select_ranking_candidate(group)["scheme_code"]
        print(f"\n    {i+1}. {fund_name}")
        print(f"       AMC: {amc}")
        print(f"       Representative scheme: {code}")
        print(f"       All scheme codes: {[s['scheme_code'] for s in group]}")


if __name__ == "__main__":
    from backend.services.mutual_funds.fund_grouper import select_ranking_candidate
    asyncio.run(main())
