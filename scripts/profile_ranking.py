"""Profile the complete ranking request to identify bottlenecks.

Measures each step of the ranking pipeline separately:
- AMFI loading
- Category normalization
- Fund grouping
- Representative selection
- TigZig Parquet query
- Metric calculation
- Normalization/scoring
- Ranking
- Total request time
"""
import asyncio
import os
import sys
import time
import resource
from collections import defaultdict

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


def get_rss_mb():
    """Get current RSS memory in MB."""
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) / 1024
    except Exception:
        pass
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def profile_category(fetcher, category, criteria_names, iterations=3):
    """Profile ranking for a specific category."""
    results = []

    for i in range(iterations):
        iter_result = {"iteration": i}
        rss_start = get_rss_mb()

        # Step 1: Get underlying funds (includes AMFI loading + grouping)
        t0 = time.time()
        underlying_funds = await fetcher.get_ranking_candidates_by_category(category)
        t1 = time.time()
        iter_result["get_underlying_funds"] = t1 - t0
        iter_result["fund_count"] = len(underlying_funds)

        if len(underlying_funds) == 0:
            return results

        # Step 2: TigZig Parquet query + metric calculation (combined in get_metrics_batch)
        t0 = time.time()
        metrics_list = await fetcher.get_metrics_batch(underlying_funds, criteria_names, chunk_size=100)
        t1 = time.time()
        iter_result["metrics_batch"] = t1 - t0
        iter_result["metrics_success"] = sum(1 for m in metrics_list if m is not None)

        # Step 3: Ranking
        from backend.services.mutual_funds.ranking import RankingEngine

        valid_metrics = [m for m in metrics_list if m is not None]
        engine = RankingEngine()
        criteria = [{"name": name, "weight": 100.0 / len(criteria_names)} for name in criteria_names]

        t0 = time.time()
        rankings = engine.rank(valid_metrics, criteria)
        t1 = time.time()
        iter_result["ranking"] = t1 - t0

        rss_end = get_rss_mb()
        iter_result["rss_delta"] = rss_end - rss_start
        iter_result["peak_rss"] = rss_end

        results.append(iter_result)

    return results


async def main():
    print("=" * 80)
    print("RANKING PERFORMANCE PROFILING")
    print("=" * 80)

    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.services.mutual_funds.category_normalizer import normalize_category
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Load schemes once to warm cache
    print("\nWarming up AMFI cache...")
    t0 = time.time()
    all_schemes = await fetcher.get_all_schemes()
    amfi_load_time = time.time() - t0
    print(f"  AMFI load time: {amfi_load_time:.2f}s ({len(all_schemes)} schemes)")

    # Get category counts
    print("\nCategory distribution:")
    category_counts = defaultdict(int)
    for s in all_schemes:
        cat = normalize_category(s.category)
        category_counts[cat] += 1

    # Select categories to profile
    categories_to_profile = []

    # Small category (< 50 funds)
    small_cats = [(c, n) for c, n in category_counts.items() if 20 <= n < 50]
    if small_cats:
        categories_to_profile.append(("Small", small_cats[0][0], small_cats[0][1]))

    # Medium category (~100-200 funds)
    medium_cats = [(c, n) for c, n in category_counts.items() if 100 <= n < 200]
    if medium_cats:
        categories_to_profile.append(("Medium", medium_cats[0][0], medium_cats[0][1]))

    # Large category (~500 funds)
    large_cats = [(c, n) for c, n in category_counts.items() if 400 <= n < 600]
    if large_cats:
        categories_to_profile.append(("Large", large_cats[0][0], large_cats[0][1]))

    # Largest category
    largest_cat = max(category_counts.items(), key=lambda x: x[1])
    categories_to_profile.append(("Largest", largest_cat[0], largest_cat[1]))

    print(f"\nCategories to profile:")
    for label, cat, count in categories_to_profile:
        print(f"  {label}: {cat} ({count} schemes)")

    # Criteria presets
    presets = {
        "Best Overall": ["1Y_return", "3Y_cagr", "5Y_cagr", "volatility", "sharpe_ratio", "maximum_drawdown"],
        "Highest Returns": ["1Y_return", "3Y_cagr", "5Y_cagr", "10Y_cagr"],
    }

    # Profile each category + preset combination
    for label, category, scheme_count in categories_to_profile:
        print(f"\n{'=' * 80}")
        print(f"Category: {category} ({label}, ~{scheme_count} schemes)")
        print(f"{'=' * 80}")

        for preset_name, criteria_names in presets.items():
            print(f"\n  Preset: {preset_name}")
            print(f"  Criteria: {criteria_names}")

            results = await profile_category(fetcher, category, criteria_names, iterations=2)

            if not results:
                print("    No funds to rank")
                continue

            # Average results
            avg_fund_count = sum(r["fund_count"] for r in results) / len(results)
            avg_get_underlying = sum(r["get_underlying_funds"] for r in results) / len(results)
            avg_metrics_batch = sum(r["metrics_batch"] for r in results) / len(results)
            avg_ranking = sum(r["ranking"] for r in results) / len(results)
            avg_total = avg_get_underlying + avg_metrics_batch + avg_ranking
            avg_rss = sum(r["peak_rss"] for r in results) / len(results)

            print(f"    Funds: {avg_fund_count:.0f}")
            print(f"    Get underlying funds: {avg_get_underlying:.2f}s")
            print(f"    Metrics batch (TigZig + calc): {avg_metrics_batch:.2f}s")
            print(f"    Ranking: {avg_ranking:.3f}s")
            print(f"    TOTAL: {avg_total:.2f}s")
            print(f"    Peak RSS: {avg_rss:.0f} MB")

    print("\n" + "=" * 80)
    print("PROFILING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
