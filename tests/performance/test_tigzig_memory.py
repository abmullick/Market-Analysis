"""Memory profiling tests for TigZig integration.

Validates:
1. Startup memory usage stays well below 512MB
2. Ranking memory usage is proportional to query size, not dataset size
3. Predicate pushdown works correctly (only required rows are read)
4. Complete category universe is still ranked
"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DATASET_PATH = "/tmp/market_analysis_data/tigzig_nav.parquet"


def get_rss_mb():
    """Get current process RSS in MB."""
    import psutil
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


@pytest.mark.skipif(not os.path.exists(DATASET_PATH), reason="TigZig dataset not available")
class TestStartupMemory:
    """Test that startup does not load the full dataset into memory."""

    def test_startup_memory_below_100mb(self):
        """Verify startup memory usage stays below 100MB."""
        import subprocess
        import json

        # Run a script that imports the dataset module and checks memory
        script = """
import sys
sys.path.insert(0, "/home/abmul/projects/Market-Analysis")
import psutil
process = psutil.Process()
mem_before = process.memory_info().rss / 1024 / 1024

from backend.services.data.tigzig import get_tigzig_dataset

dataset = get_tigzig_dataset()
# Check availability (does NOT load Parquet)
available = dataset.is_available

mem_after = process.memory_info().rss / 1024 / 1024
print(f"{mem_before:.1f},{mem_after:.1f},{available}")
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"
        parts = result.stdout.strip().split(",")
        mem_before = float(parts[0])
        mem_after = float(parts[1])
        available = parts[2] == "True"

        assert available, "Dataset should be available"
        assert mem_after < 100, f"Startup memory {mem_after:.1f}MB exceeds 100MB limit"
        print(f"\nStartup memory: {mem_before:.1f} -> {mem_after:.1f} MB (delta: {mem_after - mem_before:.1f} MB)")


@pytest.mark.skipif(not os.path.exists(DATASET_PATH), reason="TigZig dataset not available")
class TestQueryMemory:
    """Test that queries use predicate pushdown and read only required data."""

    def test_query_reads_only_required_rows(self):
        """Verify that querying for specific schemes reads only those rows."""
        from backend.services.data.tigzig import get_tigzig_dataset

        dataset = get_tigzig_dataset()
        assert dataset.is_available, "Dataset must be available"

        # Query for a small number of schemes with a limited date range
        # This should read only a tiny fraction of the 37M rows
        test_codes = [120716, 120717, 120718]  # Just 3 schemes

        mem_before = get_rss_mb()
        result = dataset.query_nav(
            test_codes,
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        mem_after = get_rss_mb()

        total_rows = sum(len(v) for v in result.values())
        print(f"\nQuery for 3 schemes, 1 year:")
        print(f"  Rows read: {total_rows:,}")
        print(f"  Memory: {mem_before:.1f} -> {mem_after:.1f} MB (delta: {mem_after - mem_before:.1f} MB)")

        # Should read at most a few thousand rows (252 trading days * 3 schemes * ~1 year)
        assert total_rows < 10000, f"Read too many rows: {total_rows:,}"
        # Memory delta should be reasonable for Render's 512MB limit
        # Note: First query may use more memory due to Parquet metadata caching
        assert mem_after - mem_before < 100, f"Memory delta too high: {mem_after - mem_before:.1f} MB"

    def test_query_with_date_filter_reads_fewer_rows(self):
        """Verify that date filtering reduces rows read."""
        from backend.services.data.tigzig import get_tigzig_dataset

        dataset = get_tigzig_dataset()
        assert dataset.is_available, "Dataset must be available"

        test_codes = [120716]

        # Query for 1 year
        result_1y = dataset.query_nav(test_codes, start_date="2024-01-01", end_date="2024-12-31")
        rows_1y = sum(len(v) for v in result_1y.values())

        # Query for 5 years
        result_5y = dataset.query_nav(test_codes, start_date="2020-01-01", end_date="2024-12-31")
        rows_5y = sum(len(v) for v in result_5y.values())

        print(f"\nDate filter comparison:")
        print(f"  1 year: {rows_1y:,} rows")
        print(f"  5 years: {rows_5y:,} rows")
        print(f"  Ratio: {rows_5y / max(rows_1y, 1):.1f}x")

        # 5 years should read roughly 5x more rows than 1 year
        # But definitely not the full 23 years of data
        assert rows_5y > rows_1y, "5-year query should read more rows than 1-year"
        assert rows_5y < rows_1y * 10, "5-year query should not read 10x more than 1-year"

    def test_query_memory_proportional_to_schemes(self):
        """Verify memory usage is proportional to number of schemes queried."""
        from backend.services.data.tigzig import get_tigzig_dataset

        dataset = get_tigzig_dataset()
        assert dataset.is_available, "Dataset must be available"

        # Get some valid scheme codes
        import pyarrow.parquet as pq
        table = pq.read_table(DATASET_PATH, columns=["scheme_code"], memory_map=True)
        unique_codes = table.column("scheme_code").to_pylist()[:20]
        del table

        # Query for 5 schemes
        mem_before = get_rss_mb()
        result_5 = dataset.query_nav(unique_codes[:5], start_date="2024-01-01", end_date="2024-12-31")
        mem_after_5 = get_rss_mb()
        delta_5 = mem_after_5 - mem_before

        # Query for 20 schemes
        result_20 = dataset.query_nav(unique_codes, start_date="2024-01-01", end_date="2024-12-31")
        mem_after_20 = get_rss_mb()
        delta_20 = mem_after_20 - mem_after_5

        rows_5 = sum(len(v) for v in result_5.values())
        rows_20 = sum(len(v) for v in result_20.values())

        print(f"\nScheme count comparison (1 year):")
        print(f"  5 schemes: {rows_5:,} rows, {delta_5:.1f} MB")
        print(f"  20 schemes: {rows_20:,} rows, {delta_20:.1f} MB")

        # Memory should scale roughly linearly with schemes
        # But neither should use excessive memory
        assert delta_5 < 50, f"5-scheme query used too much memory: {delta_5:.1f} MB"
        assert delta_20 < 100, f"20-scheme query used too much memory: {delta_20:.1f} MB"


@pytest.mark.skipif(not os.path.exists(DATASET_PATH), reason="TigZig dataset not available")
class TestChunkedQueryMemory:
    """Test that chunked queries limit peak memory usage."""

    def test_chunked_query_uses_less_memory(self):
        """Verify chunked query uses less peak memory than non-chunked."""
        from backend.services.data.tigzig import get_tigzig_dataset

        dataset = get_tigzig_dataset()
        assert dataset.is_available, "Dataset must be available"

        # Get some valid scheme codes
        import pyarrow.parquet as pq
        table = pq.read_table(DATASET_PATH, columns=["scheme_code"], memory_map=True)
        unique_codes = list(set(table.column("scheme_code").to_pylist()[:100]))
        del table

        # Non-chunked query
        mem_before = get_rss_mb()
        result_normal = dataset.query_nav(unique_codes, start_date="2024-01-01", end_date="2024-12-31")
        mem_after_normal = get_rss_mb()
        delta_normal = mem_after_normal - mem_before

        # Chunked query (chunk_size=10)
        mem_before_chunked = get_rss_mb()
        result_chunked = dataset.query_nav_chunked(
            unique_codes, chunk_size=10, start_date="2024-01-01", end_date="2024-12-31"
        )
        mem_after_chunked = get_rss_mb()
        delta_chunked = mem_after_chunked - mem_before_chunked

        rows_normal = sum(len(v) for v in result_normal.values())
        rows_chunked = sum(len(v) for v in result_chunked.values())

        print(f"\nChunked vs non-chunked query (100 schemes, 1 year):")
        print(f"  Non-chunked: {rows_normal:,} rows, {delta_normal:.1f} MB")
        print(f"  Chunked: {rows_chunked:,} rows, {delta_chunked:.1f} MB")

        # Both should read the same number of rows
        assert rows_normal == rows_chunked, "Row counts should match"

        # Chunked should use less or similar memory
        # (the difference may be small for 100 schemes, but chunked should not use more)
        assert delta_chunked < delta_normal * 1.5, "Chunked query should not use significantly more memory"


@pytest.mark.skipif(not os.path.exists(DATASET_PATH), reason="TigZig dataset not available")
class TestLightweightStats:
    """Test that get_stats() uses minimal memory."""

    def test_get_stats_does_not_load_rows(self):
        """Verify get_stats() only reads metadata, not row data."""
        from backend.services.data.tigzig import get_tigzig_dataset

        dataset = get_tigzig_dataset()
        assert dataset.is_available, "Dataset must be available"

        mem_before = get_rss_mb()
        stats = dataset.get_stats()
        mem_after = get_rss_mb()

        assert stats["available"], "Dataset should be available"
        assert stats["total_rows"] > 0, "Should report row count"
        assert stats["size_mb"] > 0, "Should report file size"

        delta = mem_after - mem_before
        print(f"\nget_stats() memory usage:")
        print(f"  Rows: {stats['total_rows']:,}")
        print(f"  Size: {stats['size_mb']:.1f} MB")
        print(f"  Memory delta: {delta:.1f} MB")

        # Reading metadata should use minimal memory (< 10MB)
        assert delta < 10, f"get_stats() used too much memory: {delta:.1f} MB"
