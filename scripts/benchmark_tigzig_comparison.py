"""Comprehensive TigZig benchmark with metric comparison."""
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

DOWNLOAD_DIR = "/tmp/tigzig_benchmark"
PARQUET_PATH = os.path.join(DOWNLOAD_DIR, "amfi_nav_master.parquet")


async def fetch_mfapi_nav(scheme_code: str, lookback_years: int = 10):
    """Fetch NAV from existing MFAPI implementation."""
    from backend.config.settings import Settings
    from backend.services.data.mfapi import MfapiClient

    settings = Settings()
    client = MfapiClient(settings=settings)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(lookback_years * 365.25))

    try:
        raw = await client.fetch_nav_history(
            scheme_code,
            start_date=start_date,
            end_date=end_date,
        )
        data = raw.get("data", [])
        result = []
        for item in data:
            date_str = item.get("date", "")
            nav_val = item.get("nav")
            if date_str and nav_val:
                # Convert DD-MM-YYYY to YYYY-MM-DD
                parts = date_str.split("-")
                if len(parts) == 3 and len(parts[2]) == 4:
                    date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
                try:
                    result.append({"date": date_str, "nav": float(nav_val)})
                except (ValueError, TypeError):
                    continue
        return result
    except Exception as e:
        return []


def fetch_tigzig_nav(scheme_code: int, lookback_years: int = 10):
    """Fetch NAV from TigZig parquet file."""
    import pyarrow.parquet as pq

    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(lookback_years * 365.25))
    start_date_str = start_date.strftime("%Y-%m-%d")

    table = pq.read_table(
        PARQUET_PATH,
        columns=["scheme_code", "date", "nav"],
        filters=[
            ("scheme_code", "=", scheme_code),
            ("date", ">=", start_date_str),
        ],
    )

    return [
        {"date": row["date"], "nav": float(row["nav"])}
        for row in table.to_pylist()
    ]


def calculate_metrics(nav_data: list[dict]) -> dict:
    """Calculate basic metrics from NAV data."""
    if len(nav_data) < 2:
        return {"error": "Insufficient data"}

    # Sort by date
    nav_data.sort(key=lambda x: x["date"])

    start_nav = nav_data[0]["nav"]
    end_nav = nav_data[-1]["nav"]
    start_date = nav_data[0]["date"]
    end_date = nav_data[-1]["date"]

    # Calculate years
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    years = (end_dt - start_dt).days / 365.25

    # Total return
    total_return = (end_nav / start_nav) - 1 if start_nav > 0 else 0

    # CAGR
    cagr = ((end_nav / start_nav) ** (1 / years)) - 1 if years > 0 and start_nav > 0 else 0

    # Daily returns
    daily_returns = []
    for i in range(1, len(nav_data)):
        prev_nav = nav_data[i - 1]["nav"]
        curr_nav = nav_data[i]["nav"]
        if prev_nav > 0:
            daily_returns.append((curr_nav / prev_nav) - 1)

    # Volatility (annualized)
    if len(daily_returns) > 1:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
        volatility = (variance ** 0.5) * (252 ** 0.5)
    else:
        volatility = 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "start_nav": start_nav,
        "end_nav": end_nav,
        "years": years,
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "observations": len(nav_data),
    }


async def main():
    print("=" * 80)
    print("TIGZIG vs MFAPI METRIC COMPARISON")
    print("=" * 80)

    # Test schemes
    test_schemes = [
        ("119594", "Aditya Birla Sun Life Frontline Equity"),
        ("119551", "Aditya Birla Sun Life Banking & PSU Debt"),
        ("119598", "HDFC Top 100 Fund"),
        ("119769", "Kotak Contra Fund"),
        ("119436", "Aditya Birla Sun Life Large & Mid Cap"),
        ("120503", "Axis ELSS Tax Saver Fund"),
        ("120465", "Axis Large Cap Fund"),
        ("119620", "Aditya Birla Sun Life Midcap Fund"),
        ("119528", "Aditya Birla Sun Life Large Cap Fund"),
        ("119606", "Aditya Birla Sun Life Gilt Fund"),
    ]

    print(f"\nTesting {len(test_schemes)} schemes...")

    results = []
    for code, name in test_schemes:
        print(f"\n  [{code}] {name}")

        # Fetch from MFAPI
        mfapi_start = time.time()
        mfapi_data = await fetch_mfapi_nav(code, lookback_years=5)
        mfapi_time = time.time() - mfapi_start

        # Fetch from TigZig
        tigzig_start = time.time()
        tigzig_data = fetch_tigzig_nav(int(code), lookback_years=5)
        tigzig_time = time.time() - tigzig_start

        # Calculate metrics
        mfapi_metrics = calculate_metrics(mfapi_data) if mfapi_data else {"error": "No data"}
        tigzig_metrics = calculate_metrics(tigzig_data) if tigzig_data else {"error": "No data"}

        print(f"    MFAPI: {len(mfapi_data)} obs in {mfapi_time:.2f}s")
        print(f"    TigZig: {len(tigzig_data)} obs in {tigzig_time:.2f}s")

        if "error" not in mfapi_metrics and "error" not in tigzig_metrics:
            print(f"    CAGR: MFAPI={mfapi_metrics['cagr']:.4f}, TigZig={tigzig_metrics['cagr']:.4f}")
            print(f"    Vol:  MFAPI={mfapi_metrics['volatility']:.4f}, TigZig={tigzig_metrics['volatility']:.4f}")

        results.append({
            "code": code,
            "name": name,
            "mfapi_obs": len(mfapi_data),
            "tigzig_obs": len(tigzig_data),
            "mfapi_time": mfapi_time,
            "tigzig_time": tigzig_time,
            "mfapi_cagr": mfapi_metrics.get("cagr"),
            "tigzig_cagr": tigzig_metrics.get("cagr"),
        })

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_mfapi_time = sum(r["mfapi_time"] for r in results)
    total_tigzig_time = sum(r["tigzig_time"] for r in results)

    print(f"\n  Total MFAPI time: {total_mfapi_time:.2f}s")
    print(f"  Total TigZig time: {total_tigzig_time:.2f}s")
    print(f"  Speedup: {total_mfapi_time / total_tigzig_time:.1f}x")

    # Category-scale benchmark
    print("\n" + "=" * 80)
    print("CATEGORY-SCALE BENCHMARK")
    print("=" * 80)

    import pyarrow.parquet as pq

    # Get all unique scheme codes
    all_codes = pq.read_table(
        PARQUET_PATH,
        columns=["scheme_code"],
    ).column("scheme_code").unique().to_pylist()

    print(f"\n  Total unique schemes in TigZig: {len(all_codes):,}")

    # Benchmark different batch sizes
    batch_sizes = [100, 500, 1000]
    for batch_size in batch_sizes:
        if batch_size > len(all_codes):
            continue

        sample_codes = all_codes[:batch_size]

        start = time.time()
        table = pq.read_table(
            PARQUET_PATH,
            columns=["scheme_code", "date", "nav"],
            filters=[("scheme_code", "in", sample_codes)],
        )
        elapsed = time.time() - start

        print(f"  {batch_size} schemes: {len(table):,} rows in {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
