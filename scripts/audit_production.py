"""Production-readiness audit of TigZig-based ranking pipeline.

Investigates:
1. TigZig coverage across categories
2. Root cause of slow MFAPI fallback
3. Representative scheme validation
4. Performance benchmarks
"""
import asyncio
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DOWNLOAD_DIR = "/tmp/market_analysis_data"
DATASET_PATH = os.path.join(DOWNLOAD_DIR, "tigzig_nav.parquet")

# Fallback to benchmark location if not in production location
if not os.path.exists(DATASET_PATH):
    DATASET_PATH = "/tmp/tigzig_benchmark/amfi_nav_master.parquet"


async def main():
    print("=" * 80)
    print("PRODUCTION-READINESS AUDIT")
    print("=" * 80)

    # Check dataset exists
    if not os.path.exists(DATASET_PATH):
        print(f"Dataset not found at {DATASET_PATH}")
        return

    import pyarrow.parquet as pq
    import pyarrow.compute as pc

    from backend.services.data.tigzig import TigZigDataset
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.services.mutual_funds.fund_grouper import FundGrouper
    from backend.services.mutual_funds.category_normalizer import normalize_category
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Initialize TigZig dataset
    dataset = TigZigDataset(data_dir=DOWNLOAD_DIR)
    if not dataset.is_available:
        # Copy from benchmark location
        import shutil
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        shutil.copy(DATASET_PATH, dataset._dataset_path)

    print(f"\nDataset available: {dataset.is_available}")
    print(f"Dataset path: {dataset._dataset_path}")
    print(f"Dataset size: {os.path.getsize(dataset._dataset_path) / (1024*1024):.1f} MB")

    # Load all TigZig scheme codes
    print("\nLoading TigZig scheme codes...")
    start = time.time()
    tigzig_table = pq.read_table(
        dataset._dataset_path,
        columns=["scheme_code"],
    )
    tigzig_codes = set(tigzig_table.column("scheme_code").to_pylist())
    tigzig_load_time = time.time() - start
    print(f"  TigZig unique codes: {len(tigzig_codes):,}")
    print(f"  Load time: {tigzig_load_time:.2f}s")

    # Load AMFI schemes and group into underlying funds
    print("\nLoading AMFI schemes...")
    start = time.time()
    schemes = await fetcher.get_all_schemes()
    amfi_load_time = time.time() - start
    print(f"  Raw AMFI schemes: {len(schemes):,}")
    print(f"  Load time: {amfi_load_time:.2f}s")

    # Group into underlying funds
    print("\nGrouping into underlying funds...")
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
    print(f"  Excluded variants: {stats['excluded_variants']:,}")

    # 1. TIGZIG COVERAGE ANALYSIS
    print("\n" + "=" * 80)
    print("1. TIGZIG COVERAGE ANALYSIS")
    print("=" * 80)

    # Check each representative scheme code
    tigzig_hits = 0
    tigzig_misses = 0
    miss_details = []

    for candidate in candidates:
        rep_code = int(candidate["_representative_scheme_code"])
        if rep_code in tigzig_codes:
            tigzig_hits += 1
        else:
            tigzig_misses += 1
            miss_details.append({
                "code": rep_code,
                "name": candidate.get("_canonical_fund_name", candidate.get("scheme_name", "")),
                "amc": candidate.get("_amc", ""),
                "category": candidate.get("_canonical_category", ""),
            })

    coverage_pct = (tigzig_hits / len(candidates) * 100) if candidates else 0

    print(f"\n  Total candidates: {len(candidates):,}")
    print(f"  TigZig hits: {tigzig_hits:,}")
    print(f"  TigZig misses: {tigzig_misses:,}")
    print(f"  Coverage: {coverage_pct:.1f}%")

    # Coverage by category
    print(f"\n  Coverage by category:")
    category_coverage = defaultdict(lambda: {"hits": 0, "misses": 0, "total": 0})
    for candidate in candidates:
        cat = normalize_category(candidate.get("_canonical_category"))
        rep_code = int(candidate["_representative_scheme_code"])
        category_coverage[cat]["total"] += 1
        if rep_code in tigzig_codes:
            category_coverage[cat]["hits"] += 1
        else:
            category_coverage[cat]["misses"] += 1

    for cat, data in sorted(category_coverage.items(), key=lambda x: -x[1]["total"]):
        pct = (data["hits"] / data["total"] * 100) if data["total"] > 0 else 0
        print(f"    {cat}: {data['hits']}/{data['total']} ({pct:.1f}%)")

    # Show misses
    if miss_details:
        print(f"\n  TigZig misses (first 20):")
        for m in miss_details[:20]:
            print(f"    [{m['code']}] {m['name'][:50]} ({m['amc']})")

    # 2. ROOT CAUSE ANALYSIS
    print("\n" + "=" * 80)
    print("2. ROOT CAUSE ANALYSIS")
    print("=" * 80)

    # Check if misses have alternative codes in their group
    print("\n  Checking if misses have alternative codes in TigZig...")
    alt_code_found = 0
    no_alt_code = 0

    for miss in miss_details[:50]:  # Check first 50 misses
        code = int(miss["code"])
        # Find the group this code belongs to
        for key, group in grouper.get_groups().items():
            group_codes = [int(s["scheme_code"]) for s in group]
            if code in group_codes:
                # Check if any other code in the group is in TigZig
                for gc in group_codes:
                    if gc in tigzig_codes:
                        alt_code_found += 1
                        break
                else:
                    no_alt_code += 1
                break

    print(f"    Alternative code found in group: {alt_code_found}")
    print(f"    No alternative code available: {no_alt_code}")

    # 3. PERFORMANCE BENCHMARK
    print("\n" + "=" * 80)
    print("3. PERFORMANCE BENCHMARK")
    print("=" * 80)

    # Find a large category
    large_category = max(category_coverage.items(), key=lambda x: x[1]["total"])
    cat_name = large_category[0]
    cat_count = large_category[1]["total"]

    print(f"\n  Testing category: {cat_name} ({cat_count} funds)")

    # Get candidates for this category
    cat_candidates = [
        c for c in candidates
        if normalize_category(c.get("_canonical_category")) == cat_name
    ]

    # Filter to only those with TigZig data
    cat_with_tigzig = [
        c for c in cat_candidates
        if int(c["_representative_scheme_code"]) in tigzig_codes
    ]

    print(f"  Funds with TigZig data: {len(cat_with_tigzig)}")

    # Benchmark TigZig query
    if cat_with_tigzig:
        codes = [int(c["_representative_scheme_code"]) for c in cat_with_tigzig]

        print(f"\n  TigZig batch query ({len(codes)} schemes)...")
        start = time.time()
        nav_results = dataset.query_nav(codes, start_date="2016-01-01")
        tigzig_query_time = time.time() - start
        total_rows = sum(len(v) for v in nav_results.values())
        print(f"    Rows retrieved: {total_rows:,}")
        print(f"    Query time: {tigzig_query_time:.2f}s")

        # Benchmark metric calculation
        print(f"\n  Metric calculation ({len(cat_with_tigzig)} funds)...")
        start = time.time()
        metrics = await fetcher.get_metrics_batch(cat_with_tigzig[:50], ["1Y_return", "3Y_cagr"])
        calc_time = time.time() - start
        successful = sum(1 for m in metrics if m is not None)
        print(f"    Successful: {successful}/{len(metrics)}")
        print(f"    Calculation time: {calc_time:.2f}s")

    # 4. MFAPI FALLBACK ANALYSIS
    print("\n" + "=" * 80)
    print("4. MFAPI FALLBACK ANALYSIS")
    print("=" * 80)

    # Test a few misses with MFAPI
    if miss_details:
        print(f"\n  Testing MFAPI fallback for {min(5, len(miss_details))} misses...")
        for miss in miss_details[:5]:
            code = miss["code"]
            print(f"\n    Testing [{code}] {miss['name'][:40]}...")

            start = time.time()
            try:
                nav = await fetcher._get_nav_history_mfapi(code, lookback_years=3)
                mfapi_time = time.time() - start
                print(f"      MFAPI returned {len(nav)} records in {mfapi_time:.2f}s")
            except Exception as e:
                mfapi_time = time.time() - start
                print(f"      MFAPI failed after {mfapi_time:.2f}s: {e}")

    # 5. SUMMARY
    print("\n" + "=" * 80)
    print("5. SUMMARY")
    print("=" * 80)

    print(f"""
TigZig Coverage:
  Total candidates: {len(candidates):,}
  TigZig hits: {tigzig_hits:,}
  TigZig misses: {tigzig_misses:,}
  Coverage: {coverage_pct:.1f}%

Performance:
  Dataset load time: {tigzig_load_time:.2f}s
  AMFI load time: {amfi_load_time:.2f}s
  TigZig query ({len(cat_with_tigzig) if cat_with_tigzig else 0} funds): {tigzig_query_time:.2f}s
  Metric calc (50 funds): {calc_time:.2f}s

Root Cause Analysis:
  - {tigzig_misses} representative codes missing from TigZig
  - {alt_code_found} have alternative codes in their group
  - {no_alt_code} have no alternative codes

Recommendations:
  1. {"Remove MFAPI from normal path" if coverage_pct > 95 else "Keep MFAPI fallback"}
  2. {"Fix representative selection" if alt_code_found > 0 else "Selection logic OK"}
  3. {"Pre-load TigZig codes into memory" if len(tigzig_codes) < 50000 else "Code set size OK"}
""")


if __name__ == "__main__":
    asyncio.run(main())
