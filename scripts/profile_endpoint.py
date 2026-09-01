"""Memory profiling for actual ranking endpoint simulation."""
import asyncio
import sys
import gc

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


def get_rss_mb():
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def profile_actual_endpoint():
    """Simulate the actual ranking endpoint flow."""
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings
    from backend.services.mutual_funds.lookback import get_required_lookback_years, get_date_range_for_lookback
    from backend.services.data.tigzig import get_tigzig_dataset, get_tigzig_metadata
    from backend.services.mutual_funds.ranking import RankingEngine
    from backend.services.mutual_funds.cache import metrics_cache

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    print("=" * 80)
    print("MEMORY PROFILING: Actual Ranking Endpoint Simulation")
    print("=" * 80)

    # Clear cache to simulate fresh start
    metrics_cache.invalidate()
    gc.collect()

    # STAGE 0: Baseline
    mem_baseline = get_rss_mb()
    print(f"\nSTAGE 0: Baseline - {mem_baseline:.1f} MB")

    # Simulate the actual endpoint flow
    category = "Debt - Corporate Bond"
    criteria_names = ["1Y_return", "sharpe_ratio"]

    # STAGE 1: Get underlying funds
    print(f"\nSTAGE 1: Get underlying funds for '{category}'")
    underlying_funds = await fetcher.get_ranking_candidates_by_category(category)
    mem_after_funds = get_rss_mb()
    print(f"  Memory: {mem_after_funds:.1f} MB (delta: {mem_after_funds - mem_baseline:.1f} MB)")
    print(f"  Funds found: {len(underlying_funds)}")

    # STAGE 2: Get metadata for screening (first load)
    print(f"\nSTAGE 2: Load metadata for screening")
    metadata_service = get_tigzig_metadata()
    metadata = await metadata_service.get_metadata()
    mem_after_metadata1 = get_rss_mb()
    print(f"  Memory: {mem_after_metadata1:.1f} MB (delta: {mem_after_metadata1 - mem_after_funds:.1f} MB)")
    print(f"  Metadata entries: {len(metadata)}")

    # STAGE 3: Calculate metrics (batch)
    print(f"\nSTAGE 3: Calculate metrics (batch)")
    gc.collect()
    mem_before_batch = get_rss_mb()
    metrics_list = await fetcher.get_metrics_batch(underlying_funds, criteria_names)
    mem_after_batch = get_rss_mb()
    successful = sum(1 for m in metrics_list if m is not None)
    print(f"  Memory: {mem_after_batch:.1f} MB (delta: {mem_after_batch - mem_before_batch:.1f} MB)")
    print(f"  Successful: {successful}/{len(underlying_funds)}")

    # STAGE 4: Rank funds
    print(f"\nSTAGE 4: Rank funds")
    engine = RankingEngine()
    criteria = [{"name": "1Y_return", "weight": 50}, {"name": "sharpe_ratio", "weight": 50}]
    rankings = engine.rank(funds=metrics_list, criteria=criteria, auto_renormalize=True)
    mem_after_rank = get_rss_mb()
    print(f"  Memory: {mem_after_rank:.1f} MB (delta: {mem_after_rank - mem_after_batch:.1f} MB)")
    print(f"  Rankings: {len(rankings)}")

    # STAGE 5: Enrich with metadata (second load - same service, should be cached)
    print(f"\nSTAGE 5: Enrich rankings with metadata")
    for r in rankings:
        code = r.get("scheme_code")
        if code:
            fund_metadata = metadata_service.lookup(int(code))
            if fund_metadata:
                r["aum_cr"] = fund_metadata.get("aaum_cr_quarterly_avg")
    mem_after_enrich = get_rss_mb()
    print(f"  Memory: {mem_after_enrich:.1f} MB (delta: {mem_after_enrich - mem_after_rank:.1f} MB)")

    # STAGE 6: Cleanup
    print(f"\nSTAGE 6: Cleanup")
    del underlying_funds
    del metrics_list
    del rankings
    del metadata
    gc.collect()
    mem_after_cleanup = get_rss_mb()
    print(f"  Memory: {mem_after_cleanup:.1f} MB (delta: {mem_after_cleanup - mem_after_enrich:.1f} MB)")

    # SUMMARY
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Stage':<40} {'Memory (MB)':<15} {'Delta (MB)':<15}")
    print("-" * 70)
    print(f"{'0. Baseline':<40} {mem_baseline:<15.1f} {'-':<15}")
    print(f"{'1. After getting funds':<40} {mem_after_funds:<15.1f} {mem_after_funds - mem_baseline:<15.1f}")
    print(f"{'2. After metadata load':<40} {mem_after_metadata1:<15.1f} {mem_after_metadata1 - mem_after_funds:<15.1f}")
    print(f"{'3. After batch metrics':<40} {mem_after_batch:<15.1f} {mem_after_batch - mem_after_metadata1:<15.1f}")
    print(f"{'4. After ranking':<40} {mem_after_rank:<15.1f} {mem_after_rank - mem_after_batch:<15.1f}")
    print(f"{'5. After enrichment':<40} {mem_after_enrich:<15.1f} {mem_after_enrich - mem_after_rank:<15.1f}")
    print(f"{'6. After cleanup':<40} {mem_after_cleanup:<15.1f} {mem_after_cleanup - mem_after_enrich:<15.1f}")
    print("-" * 70)
    print(f"{'PEAK MEMORY':<40} {max(mem_baseline, mem_after_funds, mem_after_metadata1, mem_after_batch, mem_after_rank, mem_after_enrich):<15.1f}")
    print(f"{'TOTAL INCREASE':<40} {mem_after_enrich - mem_baseline:<15.1f}")


if __name__ == "__main__":
    asyncio.run(profile_actual_endpoint())
