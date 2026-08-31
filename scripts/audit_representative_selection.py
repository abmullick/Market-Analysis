"""Audit representative scheme selection for mutual fund ranking.

Investigates:
1. Current selection logic trace
2. TigZig data fields available
3. NAV data quality metrics
4. Segregated portfolio handling
5. Alternative selection strategies comparison

Produces statistics and recommendation WITHOUT modifying production code.
"""
import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


async def main():
    print("=" * 80)
    print("REPRESENTATIVE SCHEME SELECTION AUDIT")
    print("=" * 80)

    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.services.mutual_funds.category_normalizer import normalize_category
    from backend.services.mutual_funds.fund_grouper import (
        FundGrouper,
        normalize_fund_name,
        extract_plan,
        extract_option,
        select_ranking_candidate,
    )
    from backend.services.data.tigzig import get_tigzig_dataset
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # Load all schemes
    print("\nLoading AMFI schemes...")
    raw_schemes = await fetcher.get_all_schemes()
    print(f"  Raw schemes: {len(raw_schemes)}")

    # Group into underlying funds
    print("\nGrouping into underlying funds...")
    grouper = FundGrouper()
    for scheme in raw_schemes:
        grouper.add_scheme({
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme.scheme_name,
            "amc": scheme.amc,
            "category": scheme.category,
        })

    groups = grouper.get_groups()
    candidates = grouper.get_ranking_candidates()
    print(f"  Underlying funds: {len(groups)}")
    print(f"  Ranking candidates: {len(candidates)}")

    # =========================================================================
    # STEP 1: TRACE CURRENT SELECTION LOGIC
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: CURRENT SELECTION LOGIC TRACE")
    print("=" * 80)

    # Analyze current selection outcomes
    selection_outcomes = defaultdict(int)
    plan_option_combinations = defaultdict(int)

    for candidate in candidates:
        name = candidate.get("scheme_name", "")
        plan = extract_plan(name)
        option = extract_option(name)

        plan_str = plan or "Unspecified"
        option_str = option or "Unspecified"
        combo = f"{plan_str} + {option_str}"
        plan_option_combinations[combo] += 1

    print("\n  Current representative plan/option distribution:")
    for combo, count in sorted(plan_option_combinations.items(), key=lambda x: -x[1]):
        print(f"    {combo}: {count} ({count/len(candidates)*100:.1f}%)")

    # Trace selection for sample multi-scheme groups
    print("\n  Selection trace for multi-scheme groups:")
    multi_groups = [(k, v) for k, v in groups.items() if len(v) > 1]
    for key, schemes in sorted(multi_groups, key=lambda x: -len(x[1]))[:5]:
        candidate = select_ranking_candidate(schemes)
        print(f"\n  Group: {key[1][:50]} ({len(schemes)} schemes)")
        for s in schemes:
            plan = extract_plan(s["scheme_name"]) or "-"
            option = extract_option(s["scheme_name"]) or "-"
            marker = " ← SELECTED" if s["scheme_code"] == candidate["scheme_code"] else ""
            print(f"    [{s['scheme_code']}] Plan:{plan:10s} Option:{option:10s} {s['scheme_name'][:40]}{marker}")

    # =========================================================================
    # STEP 2: INVESTIGATE TIGZIG DATA FIELDS
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: TIGZIG DATA FIELDS INVESTIGATION")
    print("=" * 80)

    dataset = get_tigzig_dataset()
    print(f"\n  TigZig dataset available: {dataset.is_available}")

    if dataset.is_available:
        # Read schema
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(dataset.dataset_path, memory_map=True)
        schema = pf.schema_arrow

        print(f"\n  TigZig schema:")
        for field in schema:
            print(f"    {field.name}: {field.type}")

        # Sample records for a few schemes
        print(f"\n  Sample TigZig records:")
        sample_codes = [int(c["_representative_scheme_code"]) for c in candidates[:5]]
        sample_data = dataset.query_nav(sample_codes[:3])

        for code, navs in sample_data.items():
            if navs:
                print(f"\n    Scheme {code}: {len(navs)} NAV records")
                print(f"      First: {navs[0]}")
                print(f"      Last:  {navs[-1]}")

        # Check for additional fields in raw parquet
        print(f"\n  Checking for additional fields in raw parquet...")
        table = pq.read_table(
            dataset.dataset_path,
            columns=None,  # All columns
            filters=[("scheme_code", "in", sample_codes[:1])],
            memory_map=True,
        )
        print(f"    Available columns: {table.column_names}")

    # =========================================================================
    # STEP 3: NAV DATA QUALITY ANALYSIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: NAV DATA QUALITY ANALYSIS")
    print("=" * 80)

    # Analyze NAV data quality for all candidates
    candidate_codes = [int(c["_representative_scheme_code"]) for c in candidates]

    # Query in chunks to avoid memory issues
    all_nav_data = {}
    chunk_size = 200
    for i in range(0, len(candidate_codes), chunk_size):
        chunk_codes = candidate_codes[i:i + chunk_size]
        chunk_data = dataset.query_nav(chunk_codes)
        all_nav_data.update(chunk_data)

    # Calculate NAV quality metrics for each candidate
    nav_metrics = {}
    for code in candidate_codes:
        navs = all_nav_data.get(code, [])
        if not navs:
            nav_metrics[code] = {
                "count": 0,
                "first_date": None,
                "last_date": None,
                "history_years": 0,
                "zero_nav_count": 0,
                "is_active": False,
            }
            continue

        dates = [n["date"] for n in navs]
        nav_values = [n["nav"] for n in navs]

        first_date = min(dates)
        last_date = max(dates)
        history_days = (datetime.strptime(last_date, "%Y-%m-%d") - datetime.strptime(first_date, "%Y-%m-%d")).days
        history_years = history_days / 365.25

        zero_nav_count = sum(1 for n in nav_values if n == 0)

        # Active if last NAV is within 30 days
        days_since_last = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
        is_active = days_since_last <= 30

        nav_metrics[code] = {
            "count": len(navs),
            "first_date": first_date,
            "last_date": last_date,
            "history_years": history_years,
            "zero_nav_count": zero_nav_count,
            "is_active": is_active,
        }

    # Distribution of NAV quality
    history_buckets = defaultdict(int)
    active_count = 0
    zero_nav_schemes = 0

    for code, metrics in nav_metrics.items():
        if metrics["history_years"] < 1:
            history_buckets["<1 year"] += 1
        elif metrics["history_years"] < 3:
            history_buckets["1-3 years"] += 1
        elif metrics["history_years"] < 5:
            history_buckets["3-5 years"] += 1
        elif metrics["history_years"] < 10:
            history_buckets["5-10 years"] += 1
        else:
            history_buckets["10+ years"] += 1

        if metrics["is_active"]:
            active_count += 1
        if metrics["zero_nav_count"] > 0:
            zero_nav_schemes += 1

    print(f"\n  NAV History Distribution:")
    for bucket in ["<1 year", "1-3 years", "3-5 years", "5-10 years", "10+ years"]:
        count = history_buckets[bucket]
        print(f"    {bucket}: {count} ({count/len(nav_metrics)*100:.1f}%)")

    print(f"\n  Active schemes (NAV within 30 days): {active_count} ({active_count/len(nav_metrics)*100:.1f}%)")
    print(f"  Schemes with zero NAV values: {zero_nav_schemes}")

    # =========================================================================
    # STEP 4: SEGREGATED PORTFOLIO ANALYSIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: SEGREGATED PORTFOLIO ANALYSIS")
    print("=" * 80)

    # Find groups with segregated portfolios
    segregated_groups = []
    for key, schemes in groups.items():
        has_segregated = any(s["scheme_name"].strip().endswith("-") for s in schemes)
        has_normal = any(not s["scheme_name"].strip().endswith("-") for s in schemes)
        if has_segregated and has_normal:
            segregated_groups.append((key, schemes))

    print(f"\n  Groups with both normal and segregated schemes: {len(segregated_groups)}")

    if segregated_groups:
        print(f"\n  Sample segregated groups:")
        for key, schemes in segregated_groups[:3]:
            candidate = select_ranking_candidate(schemes)
            print(f"\n    Group: {key[1][:50]}")
            for s in schemes:
                is_seg = s["scheme_name"].strip().endswith("-")
                marker = " ← SELECTED" if s["scheme_code"] == candidate["scheme_code"] else ""
                seg_label = " [SEGREGATED]" if is_seg else ""
                print(f"      [{s['scheme_code']}] {s['scheme_name'][:40]}{seg_label}{marker}")

    # =========================================================================
    # STEP 5: STRATEGY COMPARISON
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: SELECTION STRATEGY COMPARISON")
    print("=" * 80)

    def select_by_strategy(schemes, strategy, nav_data):
        """Select representative based on different strategies."""
        if not schemes:
            return None

        # Filter out segregated portfolios if normal schemes exist
        normal_schemes = [s for s in schemes if not s["scheme_name"].strip().endswith("-")]
        if normal_schemes:
            candidates_list = normal_schemes
        else:
            candidates_list = schemes

        if strategy == "current":
            return select_ranking_candidate(candidates_list)

        # For other strategies, we need NAV data
        scheme_nav_data = {}
        for s in candidates_list:
            code = int(s["scheme_code"])
            navs = nav_data.get(code, [])
            scheme_nav_data[s["scheme_code"]] = navs

        if strategy == "most_recent_nav":
            # Select scheme with most recent NAV date
            best = None
            best_date = None
            for s in candidates_list:
                navs = scheme_nav_data.get(s["scheme_code"], [])
                if navs:
                    last_date = max(n["date"] for n in navs)
                    if best_date is None or last_date > best_date:
                        best = s
                        best_date = last_date
            return best or candidates_list[0]

        elif strategy == "longest_history":
            # Select scheme with longest NAV history
            best = None
            best_count = 0
            for s in candidates_list:
                navs = scheme_nav_data.get(s["scheme_code"], [])
                if len(navs) > best_count:
                    best = s
                    best_count = len(navs)
            return best or candidates_list[0]

        elif strategy == "active_most_recent":
            # Select active scheme with most recent NAV
            active_schemes = []
            for s in candidates_list:
                navs = scheme_nav_data.get(s["scheme_code"], [])
                if navs:
                    last_date = max(n["date"] for n in navs)
                    days_since = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
                    if days_since <= 30:
                        active_schemes.append((s, last_date))

            if active_schemes:
                # Sort by most recent NAV date
                active_schemes.sort(key=lambda x: x[1], reverse=True)
                return active_schemes[0][0]
            # Fallback to most recent
            return select_by_strategy(candidates_list, "most_recent_nav", nav_data)

        elif strategy == "active_longest_history":
            # Select active scheme with longest history
            active_schemes = []
            for s in candidates_list:
                navs = scheme_nav_data.get(s["scheme_code"], [])
                if navs:
                    last_date = max(n["date"] for n in navs)
                    days_since = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
                    if days_since <= 30:
                        active_schemes.append((s, len(navs)))

            if active_schemes:
                # Sort by longest history
                active_schemes.sort(key=lambda x: x[1], reverse=True)
                return active_schemes[0][0]
            # Fallback to longest history
            return select_by_strategy(candidates_list, "longest_history", nav_data)

        return candidates_list[0]

    # Compare strategies
    strategies = ["current", "most_recent_nav", "longest_history", "active_most_recent", "active_longest_history"]
    strategy_results = {s: [] for s in strategies}

    for key, schemes in groups.items():
        for strategy in strategies:
            selected = select_by_strategy(schemes, strategy, all_nav_data)
            if selected:
                strategy_results[strategy].append(selected["scheme_code"])

    print(f"\n  Strategy comparison (representative selections):")
    for strategy in strategies:
        results = strategy_results[strategy]
        print(f"\n    {strategy}:")
        print(f"      Selected: {len(results)}")

    # Calculate differences between strategies
    print(f"\n  Strategy differences (how many funds get different representative):")
    current_results = set(strategy_results["current"])
    for strategy in strategies[1:]:
        other_results = set(strategy_results[strategy])
        diff = current_results.symmetric_difference(other_results)
        print(f"    {strategy} vs current: {len(diff)} different ({len(diff)/len(current_results)*100:.1f}%)")

    # =========================================================================
    # STEP 6: RECOMMENDATION
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: RECOMMENDATION")
    print("=" * 80)

    # Analyze which strategy produces best data quality
    print("\n  Data quality by strategy:")
    for strategy in strategies:
        results = strategy_results[strategy]
        total_history = 0
        active_count = 0
        for code_str in results:
            code = int(code_str)
            metrics = nav_metrics.get(code, {})
            total_history += metrics.get("history_years", 0)
            if metrics.get("is_active", False):
                active_count += 1

        avg_history = total_history / len(results) if results else 0
        print(f"\n    {strategy}:")
        print(f"      Avg history: {avg_history:.1f} years")
        print(f"      Active: {active_count} ({active_count/len(results)*100:.1f}%)" if results else "")

    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
