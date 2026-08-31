"""Audit the mutual-fund ranking universe.

Traces the full pipeline:
AMFI NAVAll.txt → category normalization → fund grouping → representative scheme selection → metrics → ranking

Documents counts, selection logic, and identifies product decisions needed.
"""
import asyncio
import os
import sys
from collections import defaultdict

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


async def main():
    print("=" * 80)
    print("MUTUAL FUND RANKING UNIVERSE AUDIT")
    print("=" * 80)

    from backend.services.mutual_funds.fetcher import MutualFundFetcher
    from backend.services.mutual_funds.category_normalizer import normalize_category, get_category_mapping
    from backend.services.mutual_funds.fund_grouper import FundGrouper, normalize_fund_name, select_ranking_candidate
    from backend.config.settings import Settings

    settings = Settings()
    fetcher = MutualFundFetcher(settings=settings)

    # =========================================================================
    # STEP 1: AMFI NAVAll.txt - Raw Scheme Records
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 1: AMFI NAVAll.txt - Raw Scheme Records")
    print("=" * 80)

    raw_schemes = await fetcher.get_all_schemes()
    print(f"\n  Raw AMFI scheme records: {len(raw_schemes)}")

    # Analyze raw scheme attributes
    amcs = set()
    raw_categories = set()
    plans = set()
    options = set()

    for s in raw_schemes:
        if s.amc:
            amcs.add(s.amc)
        if s.category:
            raw_categories.add(s.category)

        # Extract plan/option from name for analysis
        name_lower = s.scheme_name.lower()
        if "direct" in name_lower:
            plans.add("Direct")
        if "regular" in name_lower:
            plans.add("Regular")
        if "growth" in name_lower:
            options.add("Growth")
        if "idcw" in name_lower or "income" in name_lower:
            options.add("IDCW")
        if "dividend" in name_lower:
            options.add("Dividend")

    print(f"  Unique AMC names: {len(amcs)}")
    print(f"  Unique raw categories: {len(raw_categories)}")
    print(f"  Plan types detected in names: {sorted(plans)}")
    print(f"  Option types detected in names: {sorted(options)}")

    # Sample raw categories
    print(f"\n  Sample raw categories (first 20):")
    for cat in sorted(raw_categories)[:20]:
        count = sum(1 for s in raw_schemes if s.category == cat)
        print(f"    {cat}: {count} schemes")

    # =========================================================================
    # STEP 2: Category Normalization
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 2: Category Normalization")
    print("=" * 80)

    category_mapping = get_category_mapping()
    print(f"\n  Category mapping rules: {len(category_mapping)}")

    # Apply normalization
    normalized_categories = defaultdict(int)
    for s in raw_schemes:
        norm = normalize_category(s.category)
        normalized_categories[norm] += 1

    print(f"  Canonical categories: {len(normalized_categories)}")
    print(f"\n  Canonical categories (sorted by count):")
    for cat, count in sorted(normalized_categories.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count} schemes")

    # Check for unmapped categories
    unmapped = set()
    for cat in raw_categories:
        norm = normalize_category(cat)
        if norm.startswith("Other -") and cat not in ["Other", "Miscellaneous"]:
            unmapped.add((cat, norm))

    if unmapped:
        print(f"\n  ⚠️  Categories mapped to 'Other':")
        for raw, norm in sorted(unmapped):
            print(f"    {raw} → {norm}")

    # =========================================================================
    # STEP 3: Fund Grouping
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 3: Fund Grouping")
    print("=" * 80)

    grouper = FundGrouper()
    for scheme in raw_schemes:
        grouper.add_scheme({
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme.scheme_name,
            "amc": scheme.amc,
            "category": scheme.category,
        })

    groups = grouper.get_groups()
    stats = grouper.get_stats()

    print(f"\n  Underlying fund groups: {stats['total_underlying_funds']}")
    print(f"  Excluded variants: {stats['excluded_variants']}")
    print(f"  Total schemes processed: {stats['total_schemes']}")

    # Analyze group sizes
    group_sizes = defaultdict(int)
    for key, schemes in groups.items():
        group_sizes[len(schemes)] += 1

    print(f"\n  Group size distribution:")
    for size, count in sorted(group_sizes.items()):
        print(f"    {size} scheme(s): {count} groups")

    # Sample large groups
    print(f"\n  Sample groups with 5+ schemes:")
    large_groups = [(k, v) for k, v in groups.items() if len(v) >= 5]
    for key, schemes in sorted(large_groups, key=lambda x: -len(x[1]))[:5]:
        print(f"\n    Group '{key}' ({len(schemes)} schemes):")
        for s in schemes[:3]:
            print(f"      [{s['scheme_code']}] {s['scheme_name'][:60]}")
        if len(schemes) > 3:
            print(f"      ... and {len(schemes) - 3} more")

    # =========================================================================
    # STEP 4: Representative Scheme Selection
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 4: Representative Scheme Selection")
    print("=" * 80)

    candidates = grouper.get_ranking_candidates()
    print(f"\n  Ranking candidates: {len(candidates)}")

    # Analyze selection criteria
    selection_reasons = defaultdict(int)
    direct_count = 0
    regular_count = 0
    growth_count = 0
    idcw_count = 0

    for candidate in candidates:
        name = candidate.get("scheme_name", "").lower()

        if "direct" in name:
            direct_count += 1
        if "regular" in name:
            regular_count += 1
        if "growth" in name:
            growth_count += 1
        if "idcw" in name or "income" in name:
            idcw_count += 1

    print(f"\n  Plan/Option distribution in selected representatives:")
    print(f"    Direct: {direct_count} ({direct_count/len(candidates)*100:.1f}%)")
    print(f"    Regular: {regular_count} ({regular_count/len(candidates)*100:.1f}%)")
    print(f"    Growth: {growth_count} ({growth_count/len(candidates)*100:.1f}%)")
    print(f"    IDCW: {idcw_count} ({idcw_count/len(candidates)*100:.1f}%)")

    # Trace selection for a few groups
    print(f"\n  Selection trace (sample groups):")
    sample_groups = list(groups.items())[:3]
    for key, schemes in sample_groups:
        from backend.services.mutual_funds.fund_grouper import select_ranking_candidate
        candidate = select_ranking_candidate(schemes)
        print(f"\n    Group: {key}")
        for s in schemes[:5]:
            marker = " ← SELECTED" if s["scheme_code"] == candidate["scheme_code"] else ""
            print(f"      [{s['scheme_code']}] {s['scheme_name'][:50]}{marker}")
        if len(schemes) > 5:
            print(f"      ... and {len(schemes) - 5} more")

    # =========================================================================
    # STEP 5: Duplicate Detection
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 5: Duplicate Detection")
    print("=" * 80)

    # Check for duplicate canonical fund names
    canonical_names = defaultdict(list)
    for c in candidates:
        name = c.get("_canonical_fund_name", "")
        canonical_names[name].append(c)

    duplicates = {k: v for k, v in canonical_names.items() if len(v) > 1}

    if duplicates:
        print(f"\n  ⚠️  Duplicate canonical fund names: {len(duplicates)}")
        for name, dups in sorted(duplicates.items(), key=lambda x: -len(x[1]))[:10]:
            print(f"\n    '{name}' appears {len(dups)} times:")
            for d in dups:
                print(f"      [{d['_representative_scheme_code']}] AMC: {d.get('_amc', 'N/A')}")
    else:
        print(f"\n  ✅ No duplicate canonical fund names")

    # Check for duplicate scheme codes
    scheme_codes = [c["_representative_scheme_code"] for c in candidates]
    code_counts = defaultdict(int)
    for code in scheme_codes:
        code_counts[code] += 1

    dup_codes = {k: v for k, v in code_counts.items() if v > 1}
    if dup_codes:
        print(f"\n  ⚠️  Duplicate representative scheme codes: {len(dup_codes)}")
    else:
        print(f"  ✅ No duplicate representative scheme codes")

    # =========================================================================
    # STEP 6: Segregated Portfolio Handling
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 6: Segregated Portfolio Handling")
    print("=" * 80)

    # Check for segregated portfolios (trailing dashes)
    segregated = [s for s in raw_schemes if s.scheme_name.strip().endswith("-")]
    print(f"\n  Schemes with trailing dash (segregated): {len(segregated)}")

    if segregated:
        print(f"\n  Sample segregated portfolios:")
        for s in segregated[:10]:
            print(f"    [{s.scheme_code}] {s.scheme_name}")

        # Check if they're grouped correctly
        seg_groups = set()
        for s in segregated:
            norm_name = normalize_fund_name(s.scheme_name)
            for key in groups:
                if key[1] == norm_name:
                    seg_groups.add(key)
                    break

        print(f"\n  Unique groups containing segregated portfolios: {len(seg_groups)}")

    # =========================================================================
    # STEP 7: TigZig Coverage (sample only to avoid timeout)
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 7: TigZig Coverage (sample-based)")
    print("=" * 80)

    from backend.services.data.tigzig import get_tigzig_dataset

    dataset = get_tigzig_dataset()
    print(f"\n  TigZig dataset available: {dataset.is_available}")

    if dataset.is_available:
        # Sample 100 candidates for coverage check
        sample_candidates = candidates[:100]
        sample_codes = [int(c["_representative_scheme_code"]) for c in sample_candidates]

        # Query TigZig for sample codes
        tigzig_results = dataset.query_nav(sample_codes)

        covered = sum(1 for code in sample_codes if code in tigzig_results and tigzig_results[code])
        missing = [code for code in sample_codes if code not in tigzig_results or not tigzig_results[code]]

        print(f"  Sample size: {len(sample_codes)}")
        print(f"  TigZig covered: {covered} ({covered/len(sample_codes)*100:.1f}%)")
        print(f"  TigZig missing: {len(missing)}")

        if missing:
            print(f"\n  Missing codes (first 10):")
            for code in missing[:10]:
                cand = next((c for c in sample_candidates if int(c["_representative_scheme_code"]) == code), None)
                if cand:
                    print(f"    [{code}] {cand.get('_canonical_fund_name', 'N/A')[:50]}")

    # =========================================================================
    # STEP 8: UI Fund Count
    # =========================================================================
    print("\n" + "=" * 80)
    print("STEP 8: UI Fund Count Representation")
    print("=" * 80)

    print(f"\n  Raw AMFI schemes: {len(raw_schemes)}")
    print(f"  Underlying fund groups: {len(groups)}")
    print(f"  Ranking candidates: {len(candidates)}")
    print(f"  Excluded variants: {stats['excluded_variants']}")

    print(f"\n  The UI should display: {len(candidates)} ranking candidates")
    print(f"  (NOT {len(raw_schemes)} raw AMFI schemes)")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)

    print(f"""
  Pipeline Flow:
  ─────────────
  1. AMFI NAVAll.txt: {len(raw_schemes)} raw scheme records
  2. Category normalization: {len(raw_categories)} raw → {len(normalized_categories)} canonical
  3. Fund grouping: {len(raw_schemes)} schemes → {len(groups)} underlying funds
  4. Representative selection: {len(groups)} funds → {len(candidates)} ranking candidates
  5. TigZig coverage: {covered}/{len(candidates)} candidates have NAV data

  Key Metrics:
  ────────────
  - Raw AMFI schemes: {len(raw_schemes)}
  - Canonical categories: {len(normalized_categories)}
  - Underlying funds: {len(groups)}
  - Ranking candidates: {len(candidates)}
  - Excluded variants: {stats['excluded_variants']}
  - Average schemes per fund: {len(raw_schemes)/len(groups):.1f}

  Product Decisions Needed:
  ─────────────────────────""")

    if duplicates:
        print(f"  ⚠️  {len(duplicates)} duplicate canonical fund names detected")
    if missing:
        print(f"  ⚠️  {len(missing)} candidates missing from TigZig")
    if segregated:
        print(f"  ℹ️  {len(segregated)} segregated portfolio schemes handled via grouping")

    print(f"""
  UI Display Recommendation:
  ──────────────────────────
  Show: {len(candidates)} ranking candidates
  Subtitle: "Ranking {len(candidates)} unique funds from {len(raw_schemes)} AMFI schemes"
""")


if __name__ == "__main__":
    asyncio.run(main())
