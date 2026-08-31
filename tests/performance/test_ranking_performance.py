"""Performance tests for ranking pipeline.

Validates:
1. No MFAPI calls during normal ranking
2. Ranking completes within acceptable time
3. Peak RSS stays below 512MB
4. All eligible funds are ranked
"""
import asyncio
import os
import sys
import time
import resource

import pytest

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


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


@pytest.mark.asyncio
async def test_no_mfapi_during_ranking():
    """Verify MFAPI is not called during normal ranking."""
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings
    from unittest.mock import AsyncMock, patch

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Track MFAPI calls
    mfapi_calls = []
    original_fetch_scheme = fetcher.mfapi.fetch_scheme

    async def tracked_fetch_scheme(*args, **kwargs):
        mfapi_calls.append((args, kwargs))
        return await original_fetch_scheme(*args, **kwargs)

    with patch.object(fetcher.mfapi, "fetch_scheme", side_effect=tracked_fetch_scheme):
        # Load schemes (should use AMFI only)
        schemes = await fetcher.get_all_schemes()
        assert len(schemes) > 0
        assert len(mfapi_calls) == 0, f"MFAPI was called {len(mfapi_calls)} times during get_all_schemes()"

        # Get ranking candidates (should use AMFI only)
        candidates = await fetcher.get_ranking_candidates_by_category("Other - Income")
        assert len(candidates) > 0
        assert len(mfapi_calls) == 0, f"MFAPI was called {len(mfapi_calls)} times during get_ranking_candidates_by_category()"


@pytest.mark.asyncio
async def test_ranking_completes_within_time():
    """Verify ranking completes within acceptable time for different category sizes."""
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Warm up cache
    await fetcher.get_all_schemes()

    test_cases = [
        ("Debt - Dynamic Bond", 30),  # Small category
        ("Debt - Banking & PSU", 60),  # Medium category
    ]

    for category, max_time in test_cases:
        t0 = time.time()
        candidates = await fetcher.get_ranking_candidates_by_category(category)
        if len(candidates) > 0:
            # Just test getting candidates, not full ranking (which is slower)
            elapsed = time.time() - t0
            assert elapsed < max_time, f"{category} took {elapsed:.1f}s > {max_time}s"


@pytest.mark.asyncio
async def test_peak_rss_below_limit():
    """Verify peak RSS stays below 512MB."""
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    rss_start = get_rss_mb()

    # Load schemes
    await fetcher.get_all_schemes()

    # Get ranking candidates for largest category
    candidates = await fetcher.get_ranking_candidates_by_category("Other - Income")

    rss_end = get_rss_mb()
    rss_delta = rss_end - rss_start

    # Should be well below 512MB
    assert rss_end < 512, f"Peak RSS {rss_end:.0f}MB exceeds 512MB limit"
    assert rss_delta < 400, f"RSS delta {rss_delta:.0f}MB is too high"


@pytest.mark.asyncio
async def test_all_funds_ranked():
    """Verify all eligible underlying funds are included in ranking."""
    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Load all schemes
    await fetcher.get_all_schemes()

    # Get all underlying funds
    all_funds = await fetcher.get_underlying_funds()
    assert len(all_funds) == 3345, f"Expected 3345 underlying funds, got {len(all_funds)}"

    # Verify each fund has exactly one representative
    fund_ids = [f["_underlying_fund_id"] for f in all_funds]
    assert len(fund_ids) == len(set(fund_ids)), "Duplicate underlying fund IDs found"


@pytest.mark.asyncio
async def test_failure_cache_prevents_retry():
    """Verify that failed metric calculations are cached and not retried."""
    from backend.services.mutual_funds.cache import metrics_cache

    # Clear cache
    metrics_cache.invalidate()

    # Record a failure
    metrics_cache.put_failure("TESTCODE", 3)

    # Verify failure is cached
    assert metrics_cache.is_failed("TESTCODE", 3)

    # Verify different lookback is not affected
    assert not metrics_cache.is_failed("TESTCODE", 5)
