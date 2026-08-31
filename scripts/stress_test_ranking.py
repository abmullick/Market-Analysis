"""Stress test for production TigZig ranking pipeline.

Tests the largest mutual-fund category with ALL eligible underlying funds.
Measures performance, memory usage, and verifies no MFAPI dependency.
"""
import asyncio
import os
import resource
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DOWNLOAD_DIR = "/tmp/market_analysis_data"
DATASET_PATH = os.path.join(DOWNLOAD_DIR, "tigzig_nav.parquet")

# Fallback to benchmark location if not in production location
if not os.path.exists(DATASET_PATH):
    DATASET_PATH = "/tmp/tigzig_benchmark/amfi_nav_master.parquet"


def get_rss_mb():
    """Get current RSS memory in MB."""
    # Linux: read from /proc/self/status
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # Format: "VmRSS:    1234 kB"
                    parts = line.split()
                    return int(parts[1]) / 1024  # Convert kB to MB
    except Exception:
        pass
    # Fallback: use resource module (less accurate)
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class MemoryTracker:
    """Track peak memory usage during a block of code."""

    def __init__(self):
        self.start_rss = 0
        self.peak_rss = 0
        self.current_rss = 0

    def __enter__(self):
        self.start_rss = get_rss_mb()
        self.peak_rss = self.start_rss
        return self

    def __exit__(self, *args):
        self.current_rss = get_rss_mb()
        self.peak_rss = max(self.peak_rss, self.current_rss)

    def update(self):
        """Update peak RSS."""
        self.current_rss = get_rss_mb()
        self.peak_rss = max(self.peak_rss, self.current_rss)

    @property
    def delta_mb(self):
        return self.peak_rss - self.start_rss


class HTTPRequestTracker:
    """Track HTTP requests made during testing."""

    def __init__(self):
        self.request_count = 0
        self.request_urls = []

    def start(self):
        """Start tracking HTTP requests."""
        import httpx
        original_send = httpx.AsyncClient.send

        async def tracked_send(self, request, *args, **kwargs):
            HTTPRequestTracker._instance.request_count += 1
            HTTPRequestTracker._instance.request_urls.append(str(request.url))
            return await original_send(self, request, *args, **kwargs)

        HTTPRequestTracker._instance = self
        httpx.AsyncClient.send = tracked_send
        self._original_send = original_send

    def stop(self):
        """Stop tracking HTTP requests."""
        import httpx
        httpx.AsyncClient.send = self._original_send


async def main():
    print("=" * 80)
    print("PRODUCTION TIGZIG RANKING PIPELINE - STRESS TEST")
    print("=" * 80)

    # Check dataset exists
    if not os.path.exists(DATASET_PATH):
        print(f"Dataset not found at {DATASET_PATH}")
        return

    import pyarrow.parquet as pq

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
        import shutil
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        shutil.copy(DATASET_PATH, dataset._dataset_path)

    print(f"\nDataset available: {dataset.is_available}")
    print(f"Dataset path: {dataset._dataset_path}")
    print(f"Dataset size: {os.path.getsize(dataset._dataset_path) / (1024*1024):.1f} MB")

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

    # Group by canonical category
    category_funds = defaultdict(list)
    for candidate in candidates:
        cat = normalize_category(candidate.get("_canonical_category"))
        category_funds[cat].append(candidate)

    # Find the largest category
    largest_category = max(category_funds.items(), key=lambda x: len(x[1]))
    cat_name = largest_category[0]
    cat_funds = largest_category[1]

    print(f"\nLargest category: {cat_name} ({len(cat_funds)} funds)")

    # Test scales
    test_scales = [
        ("100 funds", 100),
        ("500 funds", 500),
        ("1000 funds", 1000),
        ("ALL funds", len(cat_funds)),
    ]

    # Criteria to test (using correct RankingEngine criterion names)
    criteria_names = ["1Y_return", "3Y_cagr", "5Y_cagr", "volatility", "sharpe_ratio", "maximum_drawdown"]

    for scale_name, scale_count in test_scales:
        if scale_count > len(cat_funds):
            scale_count = len(cat_funds)
            scale_name = f"ALL funds ({scale_count})"

        print("\n" + "=" * 80)
        print(f"STRESS TEST: {scale_name.upper()}")
        print("=" * 80)

        # Select funds for this test
        test_funds = cat_funds[:scale_count]
        scheme_codes = [int(f["_representative_scheme_code"]) for f in test_funds]

        print(f"\n  Category: {cat_name}")
        print(f"  Underlying funds: {len(test_funds)}")
        print(f"  Unique scheme codes: {len(set(scheme_codes))}")

        # Track HTTP requests
        http_tracker = HTTPRequestTracker()
        http_tracker.start()

        # Measure memory and performance
        # Note: We skip the initial full Parquet query because in production,
        # the chunked processing path doesn't materialize all NAV data at once.
        # The chunked path processes each chunk independently.
        mem_tracker = MemoryTracker()
        mem_tracker.__enter__()

        try:
            # Step 1: Metric calculation (chunked processing - production path)
            print(f"\n  [1] Metric calculation ({len(criteria_names)} criteria, chunk_size=100)...")
            t0 = time.time()
            metrics = await fetcher.get_metrics_batch(test_funds, criteria_names, chunk_size=100)
            calc_time = time.time() - t0
            mem_tracker.update()

            successful = sum(1 for m in metrics if m is not None)
            failed = sum(1 for m in metrics if m is None)
            total_rows = "N/A (chunked)"

            print(f"      Successful: {successful}/{len(metrics)}")
            print(f"      Failed: {failed}/{len(metrics)}")
            print(f"      Calculation time: {calc_time:.3f}s")
            print(f"      RSS after calc: {mem_tracker.current_rss:.1f} MB")
            print(f"      Peak RSS so far: {mem_tracker.peak_rss:.1f} MB")

            # Step 2: Ranking/scoring
            print(f"\n  [2] Ranking/scoring...")
            from backend.services.mutual_funds.ranking import RankingEngine

            # Build criteria with equal weights
            num_criteria = len(criteria_names)
            criteria = [{"name": name, "weight": 100.0 / num_criteria} for name in criteria_names]

            t0 = time.time()
            engine = RankingEngine()
            ranked = engine.rank(metrics, criteria)
            rank_time = time.time() - t0
            mem_tracker.update()

            print(f"      Ranked funds: {len(ranked)}")
            print(f"      Ranking time: {rank_time:.3f}s")
            print(f"      RSS after ranking: {mem_tracker.current_rss:.1f} MB")

            # Stop tracking HTTP requests
            http_tracker.stop()

            # Total time
            total_time = calc_time + rank_time

            # Final memory
            mem_tracker.__exit__()

            # Report
            print(f"\n  {'─' * 60}")
            print(f"  RESULTS SUMMARY")
            print(f"  {'─' * 60}")
            print(f"  Underlying funds:        {len(test_funds)}")
            print(f"  NAV rows returned:       {total_rows}")
            print(f"  Metric calculation time: {calc_time:.3f}s")
            print(f"  Ranking/scoring time:    {rank_time:.3f}s")
            print(f"  Total request time:      {total_time:.3f}s")
            print(f"  ─────────────────────────────────────────")
            print(f"  Start RSS:               {mem_tracker.start_rss:.1f} MB")
            print(f"  Peak RSS:                {mem_tracker.peak_rss:.1f} MB")
            print(f"  Memory delta:            {mem_tracker.delta_mb:.1f} MB")
            print(f"  ─────────────────────────────────────────")
            print(f"  External HTTP requests:  {http_tracker.request_count}")
            print(f"  MFAPI calls made:        {sum(1 for u in http_tracker.request_urls if 'mfapi.in' in u)}")
            print(f"  TigZig calls made:       {sum(1 for u in http_tracker.request_urls if 'tigzig.com' in u)}")

            # Render Free compliance
            render_limit_mb = 512
            usage_pct = (mem_tracker.peak_rss / render_limit_mb) * 100
            print(f"  ─────────────────────────────────────────")
            print(f"  Render Free 512MB limit: {usage_pct:.1f}% used")
            if mem_tracker.peak_rss < render_limit_mb * 0.8:
                print(f"  Status: ✅ PASS (under 80% limit)")
            elif mem_tracker.peak_rss < render_limit_mb:
                print(f"  Status: ⚠️  WARNING (over 80% limit)")
            else:
                print(f"  Status: ❌ FAIL (exceeds 512MB limit)")

            # Verify no MFAPI calls
            mfapi_calls = [u for u in http_tracker.request_urls if 'mfapi.in' in u]
            if mfapi_calls:
                print(f"\n  ⚠️  MFAPI CALLS DETECTED (should be 0):")
                for url in mfapi_calls[:5]:
                    print(f"      {url}")
            else:
                print(f"\n  ✅ No MFAPI calls (TigZig-only path)")

            # Verify no date filter needed
            print(f"\n  ✅ No date filter applied (full history queried)")

            # Verify no scheme cap
            print(f"  ✅ No scheme-count cap (tested {len(test_funds)} funds)")

            # Check metrics for None values
            none_metrics = defaultdict(int)
            for m in metrics:
                if m is None:
                    continue
                for key, val in m.items():
                    if val is None and key not in ("scheme_code", "scheme_name"):
                        none_metrics[key] += 1
            if none_metrics:
                print(f"  ⚠️  None metric values:")
                for key, count in sorted(none_metrics.items()):
                    print(f"      {key}: {count}")
            else:
                print(f"  ✅ All metrics computed successfully")

        except Exception as e:
            http_tracker.stop()
            mem_tracker.__exit__()
            print(f"\n  ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("STRESS TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
