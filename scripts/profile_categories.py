"""Memory profiling for different category sizes."""
import asyncio
import sys
import gc

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


def get_rss_mb():
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


async def profile_category(category_name, criteria_names=None):
    """Profile memory for a specific category."""
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings
    from backend.services.data.tigzig import get_tigzig_dataset, get_tigzig_metadata
    from backend.services.mutual_funds.cache import metrics_cache

    if criteria_names is None:
        criteria_names = ["1Y_return", "sharpe_ratio"]

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Clear cache
    metrics_cache.invalidate()
    gc.collect()

    mem_baseline = get_rss_mb()

    # Get funds
    underlying_funds = await fetcher.get_ranking_candidates_by_category(category_name)
    mem_after_funds = get_rss_mb()

    if not underlying_funds:
        print(f"\n{category_name}: No funds found")
        return

    # Load metadata
    metadata_service = get_tigzig_metadata()
    await metadata_service.get_metadata()
    mem_after_metadata = get_rss_mb()

    # Calculate metrics
    gc.collect()
    mem_before_batch = get_rss_mb()
    metrics_list = await fetcher.get_metrics_batch(underlying_funds, criteria_names)
    mem_after_batch = get_rss_mb()

    successful = sum(1 for m in metrics_list if m is not None)

    print(f"\n{'='*60}")
    print(f"Category: {category_name}")
    print(f"{'='*60}")
    print(f"  Funds: {len(underlying_funds)}")
    print(f"  Successful: {successful}")
    print(f"  Baseline: {mem_baseline:.1f} MB")
    print(f"  After funds: {mem_after_funds:.1f} MB (delta: {mem_after_funds - mem_baseline:.1f})")
    print(f"  After metadata: {mem_after_metadata:.1f} MB (delta: {mem_after_metadata - mem_after_funds:.1f})")
    print(f"  After batch: {mem_after_batch:.1f} MB (delta: {mem_after_batch - mem_before_batch:.1f})")
    print(f"  TOTAL INCREASE: {mem_after_batch - mem_baseline:.1f} MB")

    # Cleanup
    del underlying_funds
    del metrics_list
    gc.collect()


async def main():
    print("=" * 80)
    print("MEMORY PROFILING: Different Category Sizes")
    print("=" * 80)

    # Test different categories
    categories = [
        "Debt - Corporate Bond",  # Small (22 funds)
        "Debt - Dynamic Bond",    # Medium
        "Large Cap",              # Large (if exists)
        "Other - Income",         # Very large
    ]

    for category in categories:
        try:
            await profile_category(category)
        except Exception as e:
            print(f"\n{category}: Error - {e}")


if __name__ == "__main__":
    asyncio.run(main())
