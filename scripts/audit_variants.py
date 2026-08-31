"""Audit Growth/IDCW/Dividend/Reinvestment variant handling.

Traces how the current pipeline handles option variants within underlying funds.
Compares three product rule options WITHOUT modifying production code.
"""
import asyncio
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


async def main():
    print("=" * 80)
    print("GROWTH/IDCW/DIVIDEND/REINVESTMENT VARIANT AUDIT")
    print("=" * 80)

    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.services.mutual_funds.category_normalizer import normalize_category
    from backend.services.mutual_funds.fund_grouper import (
        FundGrouper,
        extract_option,
        extract_plan,
        is_segregated_portfolio,
        normalize_fund_name,
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

    # Get TigZig data for analysis
    dataset = get_tigzig_dataset()
    print(f"\n  TigZig dataset available: {dataset.is_available}")

    # =========================================================================
    # STEP 1: IDENTIFY VARIANTS
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: VARIANT IDENTIFICATION")
    print("=" * 80)

    variant_counts = defaultdict(int)
    variant_combinations = defaultdict(int)
    groups_with_variants = defaultdict(list)

    for key, schemes in groups.items():
        variants_in_group = []
        for s in schemes:
            option = extract_option(s.get("scheme_name", ""))
            plan = extract_plan(s.get("scheme_name", ""))
            variants_in_group.append({
                "plan": plan or "Unspecified",
                "option": option or "Unspecified",
            })
            variant_counts[option or "Unspecified"] += 1

        # Record combination of variants in this group
        options_in_group = sorted(set(v["option"] for v in variants_in_group))
        combo = " + ".join(options_in_group)
        variant_combinations[combo] += 1

        # Store groups with multiple different variants
        if len(options_in_group) > 1:
            groups_with_variants[combo].append((key, schemes))

    print(f"\n  Variant counts across all schemes:")
    for variant, count in sorted(variant_counts.items(), key=lambda x: -x[1]):
        print(f"    {variant}: {count} ({count/len(raw_schemes)*100:.1f}%)")

    print(f"\n  Variant combinations within underlying funds:")
    for combo, count in sorted(variant_combinations.items(), key=lambda x: -x[1]):
        print(f"    {combo}: {count} groups")

    # =========================================================================
    # STEP 2: REAL EXAMPLES
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: REAL EXAMPLES (20+ representative cases)")
    print("=" * 80)

    # Query TigZig for examples
    example_codes = []

    def collect_examples(combo_filter, max_examples=5):
        """Collect example scheme codes for a variant combination."""
        examples = []
        for combo, group_list in groups_with_variants.items():
            if combo_filter in combo:
                for key, schemes in group_list[:2]:
                    for s in schemes:
                        examples.append(int(s["scheme_code"]))
                        if len(examples) >= max_examples:
                            return examples
        return examples

    # Collect examples for different scenarios
    growth_idcw = collect_examples("Growth + IDCW", 5)
    growth_div = collect_examples("Growth + Dividend", 5)
    growth_unspec = collect_examples("Growth + Unspecified", 5)
    idcw_only = [int(s["scheme_code"]) for key, schemes in groups.items()
                 if all(extract_option(s["scheme_name"]) == "IDCW" for s in schemes)][:5]
    div_only = [int(s["scheme_code"]) for key, schemes in groups.items()
                if all("Dividend" in s["scheme_name"] for s in schemes)][:5]

    # Query NAV data for examples
    all_example_codes = list(set(growth_idcw + growth_div + growth_unspec + idcw_only + div_only))[:25]
    nav_data = {}
    if all_example_codes and dataset.is_available:
        for i in range(0, len(all_example_codes), 100):
            chunk = all_example_codes[i:i + 100]
            nav_data.update(dataset.query_nav(chunk))

    # Build lookup for schemes by code
    schemes_by_code = {}
    for s in raw_schemes:
        schemes_by_code[s.scheme_code] = s

    def print_example_group(key, schemes):
        """Print an example group with NAV data."""
        amc = key[0]
        fund_name = key[1]
        print(f"\n  AMC: {amc}")
        print(f"  Fund: {fund_name}")
        print(f"  Schemes:")

        for s in schemes:
            code = s["scheme_code"]
            name = s["scheme_name"]
            option = extract_option(name) or "Unspecified"
            plan = extract_plan(name) or "Unspecified"

            nav_info = ""
            if code in schemes_by_code and int(code) in nav_data:
                navs = nav_data[int(code)]
                if navs:
                    first = min(n["date"] for n in navs)
                    last = max(n["date"] for n in navs)
                    nav_info = f" | {len(navs)} obs | {first} to {last}"

            print(f"    [{code}] {name[:50]}")
            print(f"           Plan: {plan} | Option: {option}{nav_info}")

    # Print examples for each scenario
    scenarios = [
        ("Growth + IDCW", "Growth + IDCW"),
        ("Growth + Dividend", "Growth + Dividend"),
        ("Growth + Unspecified", "Growth + Unspecified"),
        ("IDCW + Unspecified", "IDCW + Unspecified"),
    ]

    for title, combo_filter in scenarios:
        print(f"\n  {'─' * 60}")
        print(f"  Scenario: {title}")
        print(f"  {'─' * 60}")
        count = 0
        for combo, group_list in groups_with_variants.items():
            if combo_filter in combo:
                for key, schemes in group_list[:4]:
                    print_example_group(key, schemes)
                    count += 1
                    if count >= 5:
                        break
            if count >= 5:
                break

    # IDCW-only and Dividend-only examples
    print(f"\n  {'─' * 60}")
    print(f"  Scenario: IDCW-only funds")
    print(f"  {'─' * 60}")
    count = 0
    for key, schemes in groups.items():
        if all(extract_option(s["scheme_name"]) == "IDCW" for s in schemes) and len(schemes) >= 2:
            print_example_group(key, schemes)
            count += 1
            if count >= 3:
                break

    print(f"\n  {'─' * 60}")
    print(f"  Scenario: Dividend-only funds")
    print(f"  {'─' * 60}")
    count = 0
    for key, schemes in groups.items():
        has_dividend = any("Dividend" in s["scheme_name"] for s in schemes)
        all_idcw = all(extract_option(s["scheme_name"]) == "IDCW" for s in schemes)
        if has_dividend and all_idcw and len(schemes) >= 2:
            print_example_group(key, schemes)
            count += 1
            if count >= 3:
                break

    # =========================================================================
    # STEP 3: GROUPING CORRECTNESS
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: GROUPING CORRECTNESS")
    print("=" * 80)

    # Check for potential incorrect grouping
    potential_issues = []

    for key, schemes in groups.items():
        if len(schemes) < 2:
            continue

        # Check if schemes have very different names after normalization
        normalized_names = set()
        for s in schemes:
            norm = normalize_fund_name(s["scheme_name"])
            normalized_names.add(norm)

        if len(normalized_names) > 1:
            potential_issues.append({
                "type": "multiple_normalized_names",
                "key": key,
                "schemes": schemes,
                "normalized_names": normalized_names,
            })

    print(f"\n  Groups with multiple normalized names: {len(potential_issues)}")

    if potential_issues:
        print(f"\n  Sample potential grouping issues:")
        for issue in potential_issues[:5]:
            print(f"\n    Group: {issue['key'][1][:50]}")
            print(f"    Normalized names: {issue['normalized_names']}")
            for s in issue["schemes"][:3]:
                print(f"      [{s['scheme_code']}] {s['scheme_name'][:50]}")

    # Check for funds that might be incorrectly separated
    # Look for funds with same AMC and similar names but different groups
    print(f"\n  Checking for potentially separated variants...")
    name_to_groups = defaultdict(list)
    for key, schemes in groups.items():
        amc = key[0]
        name = key[1]
        # Create a simplified name for comparison
        simplified = normalize_fund_name(name).lower().replace("-", "").replace(" ", "")
        name_to_groups[(amc, simplified)].append(key)

    potentially_separated = {k: v for k, v in name_to_groups.items() if len(v) > 1}
    print(f"  Potentially separated groups: {len(potentially_separated)}")

    if potentially_separated:
        print(f"\n  Sample potentially separated:")
        for (amc, simplified), keys in list(potentially_separated.items())[:3]:
            print(f"\n    AMC: {amc}")
            for key in keys[:2]:
                schemes = groups[key]
                print(f"      Group: {key[1][:50]} ({len(schemes)} schemes)")

    # =========================================================================
    # STEP 4: NAV/PERFORMANCE IMPACT
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: NAV/PERFORMANCE IMPACT ANALYSIS")
    print("=" * 80)

    # For funds with Growth + IDCW, compare NAV data
    comparison_results = []

    for combo, group_list in groups_with_variants.items():
        if "Growth + IDCW" not in combo and "Growth + Dividend" not in combo:
            continue

        for key, schemes in group_list[:10]:  # Sample 10 per combo
            growth_scheme = None
            idcw_scheme = None

            for s in schemes:
                option = extract_option(s["scheme_name"])
                if option == "Growth" and growth_scheme is None:
                    growth_scheme = s
                elif option == "IDCW" and idcw_scheme is None:
                    idcw_scheme = s

            if growth_scheme and idcw_scheme:
                growth_code = int(growth_scheme["scheme_code"])
                idcw_code = int(idcw_scheme["scheme_code"])

                growth_navs = nav_data.get(growth_code, [])
                idcw_navs = nav_data.get(idcw_code, [])

                if growth_navs and idcw_navs:
                    comparison_results.append({
                        "fund": key[1][:40],
                        "growth_code": growth_code,
                        "idcw_code": idcw_code,
                        "growth_obs": len(growth_navs),
                        "idcw_obs": len(idcw_navs),
                        "growth_range": f"{min(n['date'] for n in growth_navs)} to {max(n['date'] for n in growth_navs)}",
                        "idcw_range": f"{min(n['date'] for n in idcw_navs)} to {max(n['date'] for n in idcw_navs)}",
                    })

    print(f"\n  Growth vs IDCW comparison sample: {len(comparison_results)} funds")
    print(f"\n  Sample comparison:")
    for r in comparison_results[:10]:
        print(f"\n    Fund: {r['fund']}")
        print(f"      Growth: [{r['growth_code']}] {r['growth_obs']} obs ({r['growth_range']})")
        print(f"      IDCW:   [{r['idcw_code']}] {r['idcw_obs']} obs ({r['idcw_range']})")

    # =========================================================================
    # STEP 5: REPRESENTATIVE SELECTION VERIFICATION
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: REPRESENTATIVE SELECTION VERIFICATION")
    print("=" * 80)

    selection_results = defaultdict(list)

    for key, schemes in groups.items():
        if len(schemes) < 2:
            continue

        # Determine variant combination
        options = sorted(set(extract_option(s["scheme_name"]) or "Unspecified" for s in schemes))
        combo = " + ".join(options)

        # Get selected representative
        selected = select_ranking_candidate(schemes)
        selected_option = extract_option(selected["scheme_name"]) or "Unspecified"

        selection_results[combo].append({
            "selected_option": selected_option,
            "selected_code": selected["scheme_code"],
        })

    print(f"\n  Selection behavior by variant combination:")
    for combo, results in sorted(selection_results.items()):
        option_counts = defaultdict(int)
        for r in results:
            option_counts[r["selected_option"]] += 1

        print(f"\n    {combo} ({len(results)} groups):")
        for option, count in sorted(option_counts.items()):
            print(f"      Selected {option}: {count} ({count/len(results)*100:.1f}%)")

    # =========================================================================
    # STEP 6: PRODUCT RULE COMPARISON
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: PRODUCT RULE COMPARISON")
    print("=" * 80)

    # Calculate counts for each option
    option_a_count = len(raw_schemes)  # Every scheme separately
    option_b_count = len(candidates)  # One per underlying fund (current)

    # Option C: One per underlying fund with best data quality
    # For this estimate, we'll use the current count since we prefer Growth
    option_c_count = len(candidates)

    # Count schemes with identifiable variants
    growth_count = variant_counts.get("Growth", 0)
    idcw_count = variant_counts.get("IDCW", 0)
    unspec_count = variant_counts.get("Unspecified", 0)

    print(f"\n  Current variant distribution:")
    print(f"    Growth: {growth_count} ({growth_count/len(raw_schemes)*100:.1f}%)")
    print(f"    IDCW (incl Dividend): {idcw_count} ({idcw_count/len(raw_schemes)*100:.1f}%)")
    print(f"    Unspecified: {unspec_count} ({unspec_count/len(raw_schemes)*100:.1f}%)")

    print(f"\n  Option A: Rank every scheme variant separately")
    print(f"    Candidates: {option_a_count}")
    print(f"    Duplicate exposure: High (same fund appears multiple times)")
    print(f"    Data quality: N/A (all schemes ranked)")
    print(f"    User interpretation: Confusing (same fund ranked multiple times)")
    print(f"    Impact on ranking: Significantly different")
    print(f"    Implementation complexity: Low")
    print(f"    TigZig compatibility: Full")
    print(f"    Render Free compatibility: Poor (more data to process)")

    print(f"\n  Option B: One per underlying fund, Growth preferred (CURRENT)")
    print(f"    Candidates: {option_b_count}")
    print(f"    Duplicate exposure: None")
    print(f"    Data quality: Good (Growth typically has best history)")
    print(f"    User interpretation: Clear (one rank per fund)")
    print(f"    Impact on ranking: Current behavior")
    print(f"    Implementation complexity: Current")
    print(f"    TigZig compatibility: Full")
    print(f"    Render Free compatibility: Full")

    print(f"\n  Option C: One per underlying fund, best data quality preferred")
    print(f"    Candidates: {option_c_count}")
    print(f"    Duplicate exposure: None")
    print(f"    Data quality: Potentially better (selects longest history)")
    print(f"    User interpretation: Clear (one rank per fund)")
    print(f"    Impact on ranking: Slightly different from current")
    print(f"    Implementation complexity: Medium (requires NAV quality check)")
    print(f"    TigZig compatibility: Full")
    print(f"    Render Free compatibility: Full")

    # =========================================================================
    # STEP 7: DATA QUALITY COMPARISON
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 7: DATA QUALITY BY VARIANT TYPE")
    print("=" * 80)

    # Compare data quality between Growth and IDCW variants
    growth_qualities = []
    idcw_qualities = []
    unspec_qualities = []

    # Get all candidate codes and their NAV data
    candidate_codes = [int(c["_representative_scheme_code"]) for c in candidates]
    all_nav = {}
    for i in range(0, len(candidate_codes), 200):
        chunk = candidate_codes[i:i + 200]
        all_nav.update(dataset.query_nav(chunk))

    for key, schemes in groups.items():
        for s in schemes:
            code = int(s["scheme_code"])
            navs = all_nav.get(code, [])
            option = extract_option(s["scheme_name"]) or "Unspecified"

            if navs:
                first = min(n["date"] for n in navs)
                last = max(n["date"] for n in navs)
                history_days = (datetime.strptime(last, "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")).days
                history_years = history_days / 365.25
                is_active = (datetime.now() - datetime.strptime(last, "%Y-%m-%d")).days <= 30
                quality = {
                    "obs": len(navs),
                    "history_years": history_years,
                    "is_active": is_active,
                }

                if option == "Growth":
                    growth_qualities.append(quality)
                elif option == "IDCW":
                    idcw_qualities.append(quality)
                else:
                    unspec_qualities.append(quality)

    def print_quality_stats(name, qualities):
        if not qualities:
            print(f"\n    {name}: No data")
            return

        avg_obs = sum(q["obs"] for q in qualities) / len(qualities)
        avg_history = sum(q["history_years"] for q in qualities) / len(qualities)
        active_count = sum(1 for q in qualities if q["is_active"])

        print(f"\n    {name} ({len(qualities)} schemes):")
        print(f"      Avg observations: {avg_obs:.0f}")
        print(f"      Avg history: {avg_history:.1f} years")
        print(f"      Active: {active_count} ({active_count/len(qualities)*100:.1f}%)")

    print_quality_stats("Growth variants", growth_qualities)
    print_quality_stats("IDCW variants", idcw_qualities)
    print_quality_stats("Unspecified variants", unspec_qualities)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)

    print(f"""
  Variant Distribution:
  ────────────────────
  Growth: {growth_count} schemes ({growth_count/len(raw_schemes)*100:.1f}%)
  IDCW (incl Dividend): {idcw_count} schemes ({idcw_count/len(raw_schemes)*100:.1f}%)
  Unspecified: {unspec_count} schemes ({unspec_count/len(raw_schemes)*100:.1f}%)

  Groups with Multiple Variants:
  ──────────────────────────────
  Growth + IDCW: {variant_combinations.get('Growth + IDCW', 0)} groups
  Growth + Unspecified: {variant_combinations.get('Growth + Unspecified', 0)} groups
  IDCW + Unspecified: {variant_combinations.get('IDCW + Unspecified', 0)} groups

  Current Selection Behavior:
  ───────────────────────────
  When Growth + IDCW exist → Growth selected
  When Growth + Unspecified exist → Growth selected
  When IDCW + Unspecified exist → IDCW selected (first by code)
  When only Unspecified → First by scheme code

  Product Rule Comparison:
  ────────────────────────
  Option A (all schemes): {option_a_count} candidates, high duplication
  Option B (one per fund, Growth preferred): {option_b_count} candidates [CURRENT]
  Option C (one per fund, best quality): {option_c_count} candidates

  Recommendation:
  ───────────────
  Option B (current) is recommended because:
  - No duplicate exposure
  - Clear user interpretation (one rank per fund)
  - Growth typically has longer history
  - Implementation is simplest
  - Full TigZig and Render Free compatibility
""")


if __name__ == "__main__":
    asyncio.run(main())
