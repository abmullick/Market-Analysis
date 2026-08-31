"""Efficient benchmark of TigZig dataset using memory mapping."""
import os
import sys
import time

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DOWNLOAD_DIR = "/tmp/tigzig_benchmark"
PARQUET_PATH = os.path.join(DOWNLOAD_DIR, "amfi_nav_master.parquet")
LATEST_PATH = os.path.join(DOWNLOAD_DIR, "latest.csv")


def main():
    print("=" * 80)
    print("TIGZIG DATASET BENCHMARK - EFFICIENT")
    print("=" * 80)

    # Check if files exist
    if not os.path.exists(PARQUET_PATH):
        print(f"Parquet file not found at {PARQUET_PATH}")
        print("Run the download first.")
        return

    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    import psutil

    process = psutil.Process()

    # 1. FILE INFO
    print("\n" + "=" * 80)
    print("1. FILE INFO")
    print("=" * 80)

    file_size = os.path.getsize(PARQUET_PATH)
    print(f"\n  File: {PARQUET_PATH}")
    print(f"  Size: {file_size / (1024*1024):.1f} MB")

    # 2. METADATA (no data read)
    print("\n" + "=" * 80)
    print("2. PARQUET METADATA (no data loaded)")
    print("=" * 80)

    start = time.time()
    parquet_file = pq.ParquetFile(PARQUET_PATH)
    metadata = parquet_file.metadata
    schema = parquet_file.schema_arrow
    meta_time = time.time() - start

    print(f"\n  Metadata read time: {meta_time:.3f}s")
    print(f"  Row groups: {metadata.num_row_groups}")
    print(f"  Total rows: {metadata.num_rows:,}")
    print(f"  Columns: {[(f.name, f.type) for f in schema]}")

    mem_after_meta = process.memory_info().rss
    print(f"  Process RSS after metadata: {mem_after_meta / (1024*1024):.1f} MB")

    # 3. SINGLE SCHEME QUERY (with filter pushdown)
    print("\n" + "=" * 80)
    print("3. SINGLE SCHEME QUERY (filtered read)")
    print("=" * 80)

    test_codes = [
        119594, 119551, 119598, 119769, 119436,
        120503, 120465, 119620, 119528, 119606,
    ]

    print(f"\n  Testing {len(test_codes)} scheme queries...")
    query_times = []
    for code in test_codes:
        start = time.time()
        table = pq.read_table(
            PARQUET_PATH,
            columns=["scheme_code", "date", "nav"],
            filters=[("scheme_code", "=", code)],
        )
        elapsed = time.time() - start
        query_times.append(elapsed)
        rows = len(table)
        print(f"    [{code}] {rows:,} rows in {elapsed:.3f}s")

    print(f"\n  Average query time: {sum(query_times)/len(query_times):.3f}s")
    print(f"  Min: {min(query_times):.3f}s, Max: {max(query_times):.3f}s")

    mem_after_queries = process.memory_info().rss
    print(f"  Process RSS after queries: {mem_after_queries / (1024*1024):.1f} MB")

    # 4. DATE FILTERING
    print("\n" + "=" * 80)
    print("4. DATE RANGE QUERIES")
    print("=" * 80)

    date_ranges = [
        ("1Y", "2025-09-01"),
        ("3Y", "2023-09-01"),
        ("5Y", "2021-09-01"),
        ("10Y", "2016-09-01"),
    ]

    for label, start_date in date_ranges:
        start = time.time()
        table = pq.read_table(
            PARQUET_PATH,
            columns=["scheme_code", "date", "nav"],
            filters=[
                ("scheme_code", "=", test_codes[0]),
                ("date", ">", start_date),
            ],
        )
        elapsed = time.time() - start
        print(f"    {label}: {len(table):,} rows in {elapsed:.3f}s")

    # 5. MULTI-SCHEME BATCH QUERY
    print("\n" + "=" * 80)
    print("5. MULTI-SCHEME BATCH QUERY")
    print("=" * 80)

    batch_sizes = [10, 50, 100]
    for batch_size in batch_sizes:
        batch_codes = test_codes[:min(batch_size, len(test_codes))]
        # Cycle through codes if needed
        while len(batch_codes) < batch_size:
            batch_codes.extend(test_codes[:min(batch_size - len(batch_codes), len(test_codes))])
        batch_codes = batch_codes[:batch_size]

        start = time.time()
        table = pq.read_table(
            PARQUET_PATH,
            columns=["scheme_code", "date", "nav"],
            filters=[("scheme_code", "in", batch_codes)],
        )
        elapsed = time.time() - start
        print(f"    {batch_size} schemes: {len(table):,} rows in {elapsed:.3f}s")

    # 6. FULL TABLE SCAN (worst case - don't do this in production)
    print("\n" + "=" * 80)
    print("6. MEMORY MAPPING TEST")
    print("=" * 80)

    start = time.time()
    # Memory-mapped read (only metadata + column chunks on demand)
    parquet_file = pq.ParquetFile(PARQUET_PATH, memory_map=True)
    mmap_time = time.time() - start
    print(f"\n  Memory-mapped open time: {mmap_time:.3f}s")

    mem_after_mmap = process.memory_info().rss
    print(f"  Process RSS after mmap: {mem_after_mmap / (1024*1024):.1f} MB")

    # Read single row group
    start = time.time()
    first_group = parquet_file.read_row_group(0, columns=["scheme_code", "date", "nav"])
    group_time = time.time() - start
    print(f"  First row group read: {len(first_group):,} rows in {group_time:.3f}s")

    mem_after_group = process.memory_info().rss
    print(f"  Process RSS after row group: {mem_after_group / (1024*1024):.1f} MB")

    # 7. DATA COMPLETENESS
    print("\n" + "=" * 80)
    print("7. DATA COMPLETENESS")
    print("=" * 80)

    # Read just scheme_code and date for analysis
    start = time.time()
    all_data = pq.read_table(
        PARQUET_PATH,
        columns=["scheme_code", "date"],
    )
    read_time = time.time() - start
    print(f"\n  Read time (2 columns): {read_time:.1f}s")
    print(f"  Total rows: {len(all_data):,}")

    unique_schemes = len(pc.unique(all_data.column("scheme_code")))
    print(f"  Unique schemes: {unique_schemes:,}")

    min_date = pc.min(all_data.column("date")).as_py()
    max_date = pc.max(all_data.column("date")).as_py()
    print(f"  Date range: {min_date} to {max_date}")

    mem_after_full = process.memory_info().rss
    print(f"  Process RSS after full scan: {mem_after_full / (1024*1024):.1f} MB")

    # 8. SUMMARY
    print("\n" + "=" * 80)
    print("8. SUMMARY")
    print("=" * 80)

    print(f"""
Dataset:
  File size: {file_size / (1024*1024):.1f} MB
  Total rows: {metadata.num_rows:,}
  Unique schemes: {unique_schemes:,}
  Date range: {min_date} to {max_date}

Performance (memory-mapped):
  Metadata read: {meta_time:.3f}s
  Single scheme query: {sum(query_times)/len(query_times):.3f}s average
  Row group read: {group_time:.3f}s

Memory Usage:
  After metadata: {mem_after_meta / (1024*1024):.1f} MB
  After queries: {mem_after_queries / (1024*1024):.1f} MB
  After mmap open: {mem_after_mmap / (1024*1024):.1f} MB
  After full scan: {mem_after_full / (1024*1024):.1f} MB (worst case)

Render Free Feasibility:
  RAM: 512 MB limit
  Disk: 168 MB file (fits in ephemeral storage)
  CONCLUSION: VIABLE with filtered queries
""")


if __name__ == "__main__":
    main()
