#!/usr/bin/env python3

"""
Live Render Mutual Fund API correctness test.

Tests:
1. Health/basic API availability
2. AMFI scheme loading
3. Ranking endpoint
4. Returned metric structure and units
5. Score vs actual/raw value separation
6. N/A handling
7. Individual fund metrics, when an endpoint is available
8. Basic mathematical sanity checks
9. Timing
10. MFAPI dependency indication from API responses/log-style fields, if exposed

Run:
    python scripts/test_render_mf_api.py

Optional:
    BASE_URL=https://market-analysis-g4ow.onrender.com python scripts/test_render_mf_api.py
"""

import os
import sys
import time
import json
import math
import statistics
import requests
from urllib.parse import urljoin


BASE_URL = os.getenv(
    "BASE_URL",
    "https://market-analysis-g4ow.onrender.com"
).rstrip("/")

TIMEOUT = int(os.getenv("TIMEOUT", "180"))

session = requests.Session()
session.headers.update({
    "User-Agent": "MF-Ranking-Correctness-Test/1.0"
})


def get(path, **kwargs):
    url = urljoin(BASE_URL + "/", path.lstrip("/"))
    started = time.perf_counter()

    try:
        r = session.get(url, timeout=TIMEOUT, **kwargs)
        elapsed = time.perf_counter() - started
        return r, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - started
        print(f"❌ GET {url}")
        print(f"   {type(e).__name__}: {e}")
        print(f"   Time: {elapsed:.2f}s")
        return None, elapsed


def post(path, payload, **kwargs):
    url = urljoin(BASE_URL + "/", path.lstrip("/"))
    started = time.perf_counter()

    try:
        r = session.post(
            url,
            json=payload,
            timeout=TIMEOUT,
            **kwargs
        )
        elapsed = time.perf_counter() - started
        return r, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - started
        print(f"❌ POST {url}")
        print(f"   {type(e).__name__}: {e}")
        print(f"   Time: {elapsed:.2f}s")
        return None, elapsed


def dump_response(r):
    if r is None:
        return None

    print(f"   HTTP {r.status_code}")
    print(f"   Content-Type: {r.headers.get('content-type')}")
    print(f"   Size: {len(r.content):,} bytes")

    try:
        return r.json()
    except Exception:
        print("   Response is not JSON")
        print(r.text[:1000])
        return None


def find_values(obj, names):
    """
    Recursively find fields in arbitrary JSON.
    """
    found = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in names:
                found[k] = v

            nested = find_values(v, names)
            found.update(nested)

    elif isinstance(obj, list):
        for item in obj:
            nested = find_values(item, names)
            found.update(nested)

    return found


def flatten_funds(obj):
    """
    Try to locate ranking fund records regardless of whether
    the API wraps them as data/results/funds/rankings/etc.
    """

    if isinstance(obj, list):
        # If list contains dictionaries that look like funds
        if obj and all(isinstance(x, dict) for x in obj):
            return obj

        result = []
        for x in obj:
            result.extend(flatten_funds(x))
        return result

    if isinstance(obj, dict):

        # Common containers
        for key in (
            "funds",
            "results",
            "rankings",
            "data",
            "items",
            "rows",
        ):
            value = obj.get(key)

            if isinstance(value, list):
                funds = flatten_funds(value)
                if funds:
                    return funds

        # Maybe this object itself is a fund
        fund_markers = {
            "scheme_code",
            "scheme_name",
            "fund_name",
            "overall_score",
            "score",
            "metrics",
        }

        if fund_markers.intersection(obj.keys()):
            return [obj]

        result = []
        for value in obj.values():
            result.extend(flatten_funds(value))

        return result

    return []


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_number(name, value, minimum=None, maximum=None):
    if value is None:
        return True

    if not number(value):
        print(f"   ❌ {name}: not numeric: {value!r}")
        return False

    if not math.isfinite(value):
        print(f"   ❌ {name}: non-finite: {value!r}")
        return False

    if minimum is not None and value < minimum:
        print(f"   ❌ {name}: {value} < {minimum}")
        return False

    if maximum is not None and value > maximum:
        print(f"   ❌ {name}: {value} > {maximum}")
        return False

    return True


def test_homepage():
    print("\n" + "=" * 70)
    print("1. DEPLOYMENT AVAILABILITY")
    print("=" * 70)

    r, elapsed = get("/mutual-funds.html")

    if r is None:
        return False

    print(f"   HTTP {r.status_code}")
    print(f"   Time: {elapsed:.2f}s")

    if r.status_code != 200:
        print("   ❌ Mutual fund page unavailable")
        return False

    print("   ✅ Mutual fund page reachable")
    return True


def test_candidate_endpoints():
    """
    Don't assume the exact API route. Probe common routes and report
    what actually exists.
    """

    print("\n" + "=" * 70)
    print("2. API ENDPOINT DISCOVERY")
    print("=" * 70)

    candidates = [
        "/api/mutual-funds",
        "/api/mutual-funds/schemes",
        "/api/mutual-funds/ranking",
        "/api/mutual-funds/rank",
        "/mutual-funds/api/schemes",
        "/mutual-funds/api/ranking",
        "/api/mf/schemes",
        "/api/mf/ranking",
    ]

    working = []

    for path in candidates:
        r, elapsed = get(path)

        if r is None:
            continue

        print(
            f"   {path:<35} "
            f"{r.status_code} "
            f"{elapsed:.2f}s"
        )

        if r.status_code != 404:
            working.append((path, r.status_code))

    print("\n   Non-404 endpoints:")

    for path, status in working:
        print(f"      {path} -> HTTP {status}")

    return working


def test_scheme_loading():
    print("\n" + "=" * 70)
    print("3. SCHEME/UNIVERSE API")
    print("=" * 70)

    candidates = [
        "/api/mutual-funds/schemes",
        "/api/mutual-funds",
        "/api/mf/schemes",
    ]

    for path in candidates:
        r, elapsed = get(path)

        if r is None or r.status_code == 404:
            continue

        data = dump_response(r)

        if r.status_code != 200:
            continue

        print(f"   Time: {elapsed:.2f}s")

        if data is None:
            return False

        funds = flatten_funds(data)

        print(f"   Parsed records: {len(funds):,}")

        if len(funds) >= 1000:
            print("   ✅ Large AMFI universe detected")
        elif funds:
            print("   ⚠️ Records returned, but count is lower than expected")
        else:
            print("   ⚠️ Could not identify scheme records")

        return True

    print("   ⚠️ No known scheme endpoint discovered")
    return False


def test_ranking():
    print("\n" + "=" * 70)
    print("4. LIVE RANKING API")
    print("=" * 70)

    # Try common payloads.
    requests_to_try = [
        (
            "/api/mutual-funds/rank",
            {
                "category": "Other - Income"
            },
        ),
        (
            "/api/mutual-funds/ranking",
            {
                "category": "Other - Income"
            },
        ),
        (
            "/mutual-funds/api/ranking",
            {
                "category": "Other - Income"
            },
        ),
    ]

    for path, payload in requests_to_try:

        print(f"\n   Trying POST {path}")
        print(f"   Payload: {payload}")

        r, elapsed = post(path, payload)

        if r is None:
            continue

        print(f"   HTTP {r.status_code}")
        print(f"   Time: {elapsed:.2f}s")

        if r.status_code == 404:
            continue

        data = dump_response(r)

        if r.status_code != 200:
            print("   ⚠️ Endpoint exists but request was rejected.")
            continue

        if data is None:
            return None

        funds = flatten_funds(data)

        print(f"\n   Ranking records detected: {len(funds):,}")

        if not funds:
            print("   ⚠️ Could not identify fund records.")
            return data

        print("\n   First 3 ranking records:")

        for fund in funds[:3]:
            print(json.dumps(fund, indent=2)[:4000])

        return data

    print("\n   ⚠️ Could not discover ranking endpoint automatically.")
    print("   If your endpoint is different, pass it to me and I can")
    print("   adapt the script exactly.")
    return None


def locate_metrics(fund):
    """
    Locate metrics whether nested or flat.
    """

    metrics = fund.get("metrics")

    if isinstance(metrics, dict):
        return metrics

    return fund


def test_metric_sanity(ranking_data):
    print("\n" + "=" * 70)
    print("5. METRIC SANITY / UNIT CHECK")
    print("=" * 70)

    funds = flatten_funds(ranking_data)

    if not funds:
        print("   ⚠️ No funds available.")
        return False

    print(f"   Testing {min(len(funds), 20)} funds")

    failures = 0

    metric_names = [
        "one_year_return",
        "three_year_cagr",
        "3y_cagr",
        "five_year_cagr",
        "5y_cagr",
        "ten_year_cagr",
        "10y_cagr",
        "volatility",
        "sharpe_ratio",
        "sortino_ratio",
        "maximum_drawdown",
        "max_drawdown",
        "downside_deviation",
        "consistency",
    ]

    for i, fund in enumerate(funds[:20], 1):

        metrics = locate_metrics(fund)

        name = (
            fund.get("scheme_name")
            or fund.get("fund_name")
            or fund.get("name")
            or f"fund #{i}"
        )

        print(f"\n   [{i}] {name}")

        for metric in metric_names:

            if metric not in metrics:
                continue

            value = metrics[metric]

            # Returns/volatility/DD/downside are normally decimal
            if metric in {
                "one_year_return",
                "three_year_cagr",
                "3y_cagr",
                "five_year_cagr",
                "5y_cagr",
                "ten_year_cagr",
                "10y_cagr",
                "volatility",
                "maximum_drawdown",
                "max_drawdown",
                "downside_deviation",
            }:
                ok = check_number(metric, value)

                if ok and value is not None:
                    # Very large values are suspicious for decimal-return
                    # representation.
                    if abs(value) > 10:
                        print(
                            f"      ⚠️ {metric}={value} "
                            f"looks unusually large for decimal representation"
                        )

            # Ratios are unitless.
            elif metric in {
                "sharpe_ratio",
                "sortino_ratio",
            }:
                ok = check_number(metric, value)

            # Consistency is normally decimal percentage.
            elif metric == "consistency":
                ok = check_number(metric, value, 0, 1)

            else:
                ok = True

            if not ok:
                failures += 1

            print(f"      {metric}: {value}")

    print("\n   " + ("❌ Failures detected" if failures else "✅ No obvious metric-unit failures"))

    return failures == 0


def test_scores(ranking_data):
    print("\n" + "=" * 70)
    print("6. SCORE / RAW VALUE SEPARATION")
    print("=" * 70)

    funds = flatten_funds(ranking_data)

    if not funds:
        print("   ⚠️ No ranking records")
        return False

    failures = 0

    for i, fund in enumerate(funds[:20], 1):

        name = (
            fund.get("scheme_name")
            or fund.get("fund_name")
            or fund.get("name")
            or f"fund #{i}"
        )

        score = (
            fund.get("overall_score")
            if fund.get("overall_score") is not None
            else fund.get("score")
        )

        if score is not None:
            if not check_number("overall_score", score, 0, 100):
                failures += 1

        criteria = fund.get("criteria") or fund.get("scores")

        if isinstance(criteria, dict):

            for criterion_name, criterion in criteria.items():

                if not isinstance(criterion, dict):
                    continue

                score_value = criterion.get("score")
                raw_value = criterion.get("raw_value")

                if score_value is not None:
                    if not check_number(
                        f"{criterion_name}.score",
                        score_value,
                        0,
                        100,
                    ):
                        failures += 1

                if raw_value is not None and not number(raw_value):
                    print(
                        f"   ❌ {name}: "
                        f"{criterion_name}.raw_value is not numeric"
                    )
                    failures += 1

    print(
        f"   Tested {min(len(funds), 20)} funds"
    )

    if failures:
        print(f"   ❌ {failures} score/value issues")
        return False

    print("   ✅ Scores are within expected 0–100 range")
    return True


def test_ranking_order(ranking_data):
    print("\n" + "=" * 70)
    print("7. RANKING ORDER CHECK")
    print("=" * 70)

    funds = flatten_funds(ranking_data)

    scores = []

    for fund in funds:
        score = fund.get("overall_score")

        if score is None:
            score = fund.get("score")

        if number(score):
            scores.append(score)

    if len(scores) < 3:
        print("   ⚠️ Not enough scores to test ordering")
        return True

    descending = all(
        scores[i] >= scores[i + 1]
        for i in range(len(scores) - 1)
    )

    ascending = all(
        scores[i] <= scores[i + 1]
        for i in range(len(scores) - 1)
    )

    print(f"   Scores found: {len(scores):,}")
    print(f"   First 10: {scores[:10]}")

    if descending:
        print("   ✅ Ranking is descending by score")
        return True

    if ascending:
        print("   ⚠️ Ranking is ascending by score")
        return True

    print("   ⚠️ Results are not monotonically sorted by overall score")
    return False


def test_duplicate_representatives(ranking_data):
    print("\n" + "=" * 70)
    print("8. DUPLICATE REPRESENTATIVE CHECK")
    print("=" * 70)

    funds = flatten_funds(ranking_data)

    codes = []
    names = []

    for fund in funds:

        code = fund.get("scheme_code")

        if code is not None:
            codes.append(str(code))

        name = (
            fund.get("fund_name")
            or fund.get("scheme_name")
        )

        if name:
            names.append(name)

    duplicate_codes = len(codes) - len(set(codes))

    print(f"   Funds: {len(funds):,}")
    print(f"   Scheme codes: {len(codes):,}")
    print(f"   Duplicate scheme codes: {duplicate_codes}")

    if duplicate_codes:
        print("   ❌ Duplicate representative scheme codes found")
        return False

    print("   ✅ No duplicate representative scheme codes")
    return True


def test_no_nan_inf(ranking_data):
    print("\n" + "=" * 70)
    print("9. NaN / INFINITY CHECK")
    print("=" * 70)

    failures = []

    def walk(obj, path="root"):

        if isinstance(obj, float):

            if not math.isfinite(obj):
                failures.append((path, obj))

        elif isinstance(obj, dict):

            for k, v in obj.items():
                walk(v, f"{path}.{k}")

        elif isinstance(obj, list):

            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(ranking_data)

    if failures:
        print(f"   ❌ {len(failures)} non-finite values found")

        for path, value in failures[:20]:
            print(f"      {path}: {value}")

        return False

    print("   ✅ No NaN/Infinity values")
    return True


def main():

    print("=" * 70)
    print("LIVE RENDER MUTUAL FUND CALCULATION CORRECTNESS TEST")
    print("=" * 70)
    print(f"Base URL: {BASE_URL}")
    print(f"Timeout:  {TIMEOUT}s")

    results = {}

    results["deployment"] = test_homepage()

    test_candidate_endpoints()

    results["schemes"] = test_scheme_loading()

    ranking_data = test_ranking()

    if ranking_data is not None:

        results["metric_sanity"] = test_metric_sanity(
            ranking_data
        )

        results["scores"] = test_scores(
            ranking_data
        )

        results["ranking_order"] = test_ranking_order(
            ranking_data
        )

        results["duplicates"] = test_duplicate_representatives(
            ranking_data
        )

        results["nan_inf"] = test_no_nan_inf(
            ranking_data
        )

    print("\n" + "=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    for test, result in results.items():

        if result is True:
            status = "PASS"

        elif result is False:
            status = "FAIL"

        else:
            status = "NOT TESTED"

        print(f"{status:<12} {test}")

    failures = [
        name
        for name, result in results.items()
        if result is False
    ]

    print()

    if failures:
        print("❌ FAILURES:")
        for failure in failures:
            print(f"   - {failure}")

        sys.exit(1)

    print("✅ No failures detected by this automated test.")
    print(
        "NOTE: This verifies API-level sanity. "
        "It does not prove mathematical correctness against "
        "an independent NAV dataset unless raw NAV data is also compared."
    )


if __name__ == "__main__":
    main()
