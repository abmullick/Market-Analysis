"""Profile Parquet query memory usage and efficiency.

Investigates:
- Row group access patterns
- Predicate pushdown efficiency
- Column projection efficiency
- Memory usage during read vs metric calculation
"""
import os
import sys
import time
import resource

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DOWNLOAD_DIR = "/tmp/market_analysis_data"
DATASET_PATH = os.path.join(DOWNLOAD_DIR, "tigzig_nav.parquet")


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


def main():
    print("=" * 80)
    print("PARQUET QUERY PROFILING")
    print("=" * 80)

    if not os.path.exists(DATASET_PATH):
        print(f"Dataset not found at {DATASET_PATH}")
        return

    import pyarrow.parquet as pq
    import pyarrow.compute as pc

    # Profile 1: Dataset metadata
    print("\n[1] Dataset Metadata")
    print("-" * 40)

    pf = pq.ParquetFile(DATASET_PATH, memory_map=True)
    metadata = pf.metadata

    print(f"  File size: {os.path.getsize(DATASET_PATH) / (1024*1024):.1f} MB")
    print(f"  Total rows: {metadata.num_rows:,}")
    print(f"  Row groups: {metadata.num_row_groups}")
    print(f"  Columns: {pf.schema_arrow.names}")

    # Row group details
    print(f"\n  Row group details:")
    for i in range(metadata.num_row_groups):
        rg = metadata.row_group(i)
        print(f"    RG {i}: {rg.num_rows:,} rows, {rg.total_byte_size / (1024*1024):.1f} MB")

    # Profile 2: Column projection
    print("\n[2] Column Projection Efficiency")
    print("-" * 40)

    # Sample scheme codes for testing
    sample_codes = list(range(100001, 100100))  # 100 codes

    # Read all columns
    rss_before = get_rss_mb()
    t0 = time.time()
    table_all = pq.read_table(
        DATASET_PATH,
        columns=None,  # All columns
        filters=[("scheme_code", "in", sample_codes)],
        memory_map=True,
    )
    time_all = time.time() - t0
    rss_after_all = get_rss_mb()

    rows_all = len(table_all)
    cols_all = table_all.column_names
    del table_all

    print(f"  All columns ({len(cols_all)}):")
    print(f"    Rows: {rows_all:,}")
    print(f"    Time: {time_all:.3f}s")
    print(f"    RSS delta: {rss_after_all - rss_before:.1f} MB")

    # Read only required columns
    rss_before = get_rss_mb()
    t0 = time.time()
    table_required = pq.read_table(
        DATASET_PATH,
        columns=["scheme_code", "date", "nav"],
        filters=[("scheme_code", "in", sample_codes)],
        memory_map=True,
    )
    time_required = time.time() - t0
    rss_after_required = get_rss_mb()

    rows_required = len(table_required)
    cols_required = table_required.column_names
    del table_required

    print(f"\n  Required columns only ({len(cols_required)}):")
    print(f"    Rows: {rows_required:,}")
    print(f"    Time: {time_required:.3f}s")
    print(f"    RSS delta: {rss_after_required - rss_before:.1f} MB")
    print(f"    Memory savings: {(1 - (rss_after_required - rss_before) / (rss_after_all - rss_before)) * 100:.1f}%")

    # Profile 3: Predicate pushdown
    print("\n[3] Predicate Pushdown Analysis")
    print("-" * 40)

    # Test with different filter sizes
    filter_sizes = [10, 50, 100, 500, 1000]

    for size in filter_sizes:
        codes = list(range(100001, 100001 + size))

        rss_before = get_rss_mb()
        t0 = time.time()
        table = pq.read_table(
            DATASET_PATH,
            columns=["scheme_code", "date", "nav"],
            filters=[("scheme_code", "in", codes)],
            memory_map=True,
        )
        query_time = time.time() - t0
        rss_after = get_rss_mb()

        rows = len(table)
        del table

        print(f"  Filter {size:4d} codes: {rows:8,} rows, {query_time:.3f}s, RSS +{rss_after - rss_before:.1f} MB")

    # Profile 4: Row group access patterns
    print("\n[4] Row Group Access Patterns")
    print("-" * 40)

    # Check which row groups contain our sample codes
    sample_codes_set = set(range(100001, 100100))

    for i in range(metadata.num_row_groups):
        rg = metadata.row_group(i)
        # Check if scheme_code column has stats
        for col_idx in range(rg.num_columns):
            col = rg.column(col_idx)
            if col.meta_data.path_in_schema == "scheme_code":
                stats = col.meta_data.statistics
                if stats:
                    min_val = stats.min_value
                    max_val = stats.max_value
                    # Check overlap with our sample
                    if min_val in sample_codes_set or max_val in sample_codes_set:
                        print(f"  RG {i}: scheme_code range [{min_val}, {max_val}] - OVERLAPS")
                    break

    # Profile 5: Memory during metric calculation
    print("\n[5] Memory During Metric Calculation")
    print("-" * 40)

    from backend.services.mutual_funds.calculator import MetricsCalculator
    from backend.models.mutual_fund import NAVRecord

    # Query 100 schemes
    codes = list(range(100001, 100100))
    rss_before = get_rss_mb()
    t0 = time.time()
    table = pq.read_table(
        DATASET_PATH,
        columns=["scheme_code", "date", "nav"],
        filters=[("scheme_code", "in", codes)],
        memory_map=True,
    )
    query_time = time.time() - t0
    rss_after_query = get_rss_mb()

    print(f"  Query 100 schemes:")
    print(f"    Rows: {len(table):,}")
    print(f"    Query time: {query_time:.3f}s")
    print(f"    RSS after query: {rss_after_query:.1f} MB (+{rss_after_query - rss_before:.1f})")

    # Convert to per-scheme NAV
    scheme_codes_col = table.column("scheme_code").to_pylist()
    dates_col = table.column("date").to_pylist()
    navs_col = table.column("nav").to_pylist()
    del table  # Release the Arrow table

    rss_after_convert = get_rss_mb()
    print(f"    RSS after Arrow→Python convert: {rss_after_convert:.1f} MB")

    # Group by scheme
    nav_by_scheme = {}
    for code, date, nav in zip(scheme_codes_col, dates_col, navs_col):
        if code not in nav_by_scheme:
            nav_by_scheme[code] = []
        nav_by_scheme[code].append(NAVRecord(date=date, nav=float(nav)))

    del scheme_codes_col, dates_col, navs_col
    rss_after_group = get_rss_mb()
    print(f"    RSS after grouping: {rss_after_group:.1f} MB")

    # Calculate metrics for each scheme
    calc_times = []
    for code, nav_records in nav_by_scheme.items():
        t0 = time.time()
        calc = MetricsCalculator(scheme_code=str(code), nav_records=nav_records)
        metrics = calc.calculate()
        calc_times.append(time.time() - t0)

    rss_after_calc = get_rss_mb()
    print(f"    RSS after metric calc: {rss_after_calc:.1f} MB")
    print(f"    Avg calc time per scheme: {sum(calc_times)/len(calc_times)*1000:.1f}ms")

    # Profile 6: Streaming/batch reading
    print("\n[6] Streaming/Batch Reading (PyArrow)")
    print("-" * 40)

    # Test with record batches
    rss_before = get_rss_mb()
    t0 = time.time()

    pf = pq.ParquetFile(DATASET_PATH, memory_map=True)
    total_rows = 0
    batch_count = 0

    for batch in pf.iter_batches(
        batch_size=10000,
        columns=["scheme_code", "date", "nav"],
        filter=pc.field("scheme_code").isin(codes),
    ):
        total_rows += len(batch)
        batch_count += 1

    iter_time = time.time() - t0
    rss_after = get_rss_mb()

    print(f"  iter_batches (batch_size=10000):")
    print(f"    Total rows: {total_rows:,}")
    print(f"    Batches: {batch_count}")
    print(f"    Time: {iter_time:.3f}s")
    print(f"    RSS delta: {rss_after - rss_before:.1f} MB")

    print("\n" + "=" * 80)
    print("PROFILING COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
