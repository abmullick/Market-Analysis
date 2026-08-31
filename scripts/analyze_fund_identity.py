"""Comprehensive fund identity analysis from AMFI data.

Analyzes the relationship between multiple AMFI scheme entries
to determine how to group them into underlying funds.
"""
import asyncio
import json
import re
import sys
from collections import defaultdict
from typing import Any, Optional

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


def parse_amfi_text(text: str) -> list[dict[str, Any]]:
    """Parse AMFI NAVAll.txt format into structured data."""
    schemes = []
    current_category = None
    current_amc = None
    seen = set()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("Open Ended Schemes(") or stripped.startswith("Close Ended Schemes("):
            current_category = stripped.split("(")[1].rstrip(")") if "(" in stripped else stripped
            current_amc = None
            continue

        if ";" not in stripped:
            if current_category and not stripped.startswith("Scheme Code"):
                current_amc = stripped
            continue

        if stripped.startswith("Scheme Code"):
            continue

        parts = stripped.split(";")
        if len(parts) < 7:
            continue

        scheme_code = parts[0].strip()
        scheme_name = parts[3].strip()
        if not scheme_code or not scheme_name or scheme_code in seen:
            continue
        seen.add(scheme_code)

        # Extract ISIN if available (parts[4] or parts[5] may contain ISIN)
        isin = None
        if len(parts) > 4:
            potential_isin = parts[4].strip()
            if re.match(r'^[A-Z]{2}[A-Z0-9]{9}\d$', potential_isin):
                isin = potential_isin

        schemes.append({
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "amc": current_amc,
            "category": current_category,
            "isin": isin,
            "raw_parts": parts,
        })

    return schemes


def extract_plan_option(scheme_name: str) -> dict[str, Optional[str]]:
    """Extract plan and option from scheme name.

    Returns dict with 'plan' and 'option' keys.
    """
    name = scheme_name.strip()

    # Extract plan
    plan = None
    plan_patterns = [
        (r'\bDirect Plan\b', 'Direct'),
        (r'\bDirect\b', 'Direct'),
        (r'\bRegular Plan\b', 'Regular'),
        (r'\bRegular\b', 'Regular'),
    ]
    for pattern, plan_type in plan_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            plan = plan_type
            break

    # Extract option
    option = None
    option_patterns = [
        (r'\bGrowth\b', 'Growth'),
        (r'\bIDCW\b', 'IDCW'),
        (r'\bDividend\b', 'IDCW'),
        (r'\bReinvestment\b', 'Reinvestment'),
        (r'\bPayout\b', 'Payout'),
    ]
    for pattern, option_type in option_patterns:
        if re.search(pattern, name, re.IGNORECASE):
            option = option_type
            break

    return {"plan": plan, "option": option}


def normalize_fund_name(scheme_name: str) -> str:
    """Extract the underlying fund name by removing plan/option suffixes."""
    name = scheme_name.strip()

    # Remove common suffixes in order
    suffixes = [
        r'\s*-\s*Direct Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Regular Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Direct\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Regular\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Direct Plan\s*$',
        r'\s*-\s*Regular Plan\s*$',
        r'\s*-\s*Direct\s*$',
        r'\s*-\s*Regular\s*$',
        r'\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Regular Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Regular\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct Plan\s*$',
        r'\s+Regular Plan\s*$',
        r'\s+Direct\s*$',
        r'\s+Regular\s*$',
        r'\s+(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
    ]

    for suffix in suffixes:
        match = re.search(suffix, name, re.IGNORECASE)
        if match:
            name = name[:match.start()]
            break

    # Clean up
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)

    return name


async def main():
    from backend.config.settings import Settings
    from backend.services.data.amfi import AmfiClient

    settings = Settings()
    amfi_client = AmfiClient(settings=settings)

    print("Fetching AMFI data...")
    text = await amfi_client.fetch_nav_all()
    schemes = parse_amfi_text(text)

    print(f"Total schemes: {len(schemes)}")

    # Enrich schemes with plan/option info
    for s in schemes:
        po = extract_plan_option(s["scheme_name"])
        s["plan"] = po["plan"]
        s["option"] = po["option"]
        s["fund_name"] = normalize_fund_name(s["scheme_name"])

    # Group by AMC + fund_name
    fund_groups: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        key = f"{s['amc']}||{s['fund_name']}"
        fund_groups[key].append(s)

    # Find groups with multiple entries
    multi_groups = {k: v for k, v in fund_groups.items() if len(v) > 1}
    single_groups = {k: v for k, v in fund_groups.items() if len(v) == 1}

    print(f"\nTotal unique underlying funds: {len(fund_groups)}")
    print(f"Single-entry funds: {len(single_groups)}")
    print(f"Multi-entry funds: {len(multi_groups)}")

    # Analyze plan/option distribution
    plan_dist = defaultdict(int)
    option_dist = defaultdict(int)
    combo_dist = defaultdict(int)

    for s in schemes:
        plan_dist[s["plan"]] += 1
        option_dist[s["option"]] += 1
        combo_dist[(s["plan"], s["option"])] += 1

    print("\n" + "=" * 80)
    print("PLAN DISTRIBUTION")
    print("=" * 80)
    for plan, count in sorted(plan_dist.items(), key=lambda x: -x[1]):
        print(f"  {plan or 'Unspecified'}: {count}")

    print("\n" + "=" * 80)
    print("OPTION DISTRIBUTION")
    print("=" * 80)
    for option, count in sorted(option_dist.items(), key=lambda x: -x[1]):
        print(f"  {option or 'Unspecified'}: {count}")

    print("\n" + "=" * 80)
    print("PLAN+OPTION COMBINATION DISTRIBUTION")
    print("=" * 80)
    for combo, count in sorted(combo_dist.items(), key=lambda x: -x[1]):
        plan, option = combo
        print(f"  {plan or 'Unspecified'} + {option or 'Unspecified'}: {count}")

    # Analyze multi-entry groups
    print("\n" + "=" * 80)
    print("MULTI-ENTRY FUND ANALYSIS")
    print("=" * 80)

    # Categorize multi-entry groups
    multi_only_growth = []
    multi_only_idcw = []
    multi_both_options = []
    multi_direct_regular = []
    multi_complex = []

    for key, group in multi_groups.items():
        plans = set(s["plan"] for s in group)
        options = set(s["option"] for s in group)

        has_direct_regular = len(plans) > 1
        has_both_options = len(options) > 1

        if has_direct_regular and has_both_options:
            multi_complex.append((key, group))
        elif has_direct_regular:
            multi_direct_regular.append((key, group))
        elif has_both_options:
            multi_both_options.append((key, group))
        elif options == {"Growth"}:
            multi_only_growth.append((key, group))
        elif options == {"IDCW"}:
            multi_only_idcw.append((key, group))

    print(f"\nMulti-entry with both Direct/Regular AND Growth/IDCW: {len(multi_complex)}")
    print(f"Multi-entry with only Direct/Regular variants: {len(multi_direct_regular)}")
    print(f"Multi-entry with only Growth/IDCW variants: {len(multi_both_options)}")
    print(f"Multi-entry with only Growth (no IDCW): {len(multi_only_growth)}")
    print(f"Multi-entry with only IDCW (no Growth): {len(multi_only_idcw)}")

    # Show examples
    print("\n" + "=" * 80)
    print("EXAMPLE: Direct + Regular + Growth + IDCW (Complex)")
    print("=" * 80)

    for key, group in sorted(multi_complex, key=lambda x: -len(x[1]))[:10]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        for s in sorted(group, key=lambda x: x["scheme_name"]):
            print(f"  [{s['scheme_code']}] {s['scheme_name']}")
            print(f"      Plan: {s['plan']}, Option: {s['option']}, Category: {s['category']}")

    print("\n" + "=" * 80)
    print("EXAMPLE: Direct + Regular only")
    print("=" * 80)

    for key, group in sorted(multi_direct_regular, key=lambda x: -len(x[1]))[:10]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        for s in sorted(group, key=lambda x: x["scheme_name"]):
            print(f"  [{s['scheme_code']}] {s['scheme_name']}")
            print(f"      Plan: {s['plan']}, Option: {s['option']}, Category: {s['category']}")

    print("\n" + "=" * 80)
    print("EXAMPLE: Growth + IDCW only")
    print("=" * 80)

    for key, group in sorted(multi_both_options, key=lambda x: -len(x[1]))[:10]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        for s in sorted(group, key=lambda x: x["scheme_name"]):
            print(f"  [{s['scheme_code']}] {s['scheme_name']}")
            print(f"      Plan: {s['plan']}, Option: {s['option']}, Category: {s['category']}")

    # Check for similar names that might be different funds
    print("\n" + "=" * 80)
    print("SIMILAR NAMES ANALYSIS")
    print("=" * 80)

    # Find fund names that are very similar but might be different
    fund_names = {}
    for key, group in fund_groups.items():
        amc, fund_name = key.split("||")
        normalized = fund_name.lower().strip()
        if normalized not in fund_names:
            fund_names[normalized] = []
        fund_names[normalized].append((key, group))

    # Find names that appear in multiple AMCs
    cross_amc = {k: v for k, v in fund_names.items() if len(v) > 1}
    print(f"\nFund names appearing in multiple AMCs: {len(cross_amc)}")

    for name, entries in sorted(cross_amc, key=lambda x: -len(x[1]))[:10]:
        print(f"\n  '{name}':")
        for key, group in entries:
            amc, fund_name = key.split("||")
            print(f"    AMC: {amc}, Schemes: {len(group)}")

    # Check category consistency within fund groups
    print("\n" + "=" * 80)
    print("CATEGORY CONSISTENCY WITHIN FUND GROUPS")
    print("=" * 80)

    inconsistent_categories = []
    for key, group in multi_groups.items():
        categories = set(s["category"] for s in group)
        if len(categories) > 1:
            inconsistent_categories.append((key, group, categories))

    print(f"\nFund groups with inconsistent categories: {len(inconsistent_categories)}")

    for key, group, categories in inconsistent_categories[:10]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        print(f"Categories: {categories}")
        for s in group:
            print(f"  [{s['scheme_code']}] {s['scheme_name']} -> {s['category']}")

    # Calculate ranking universe under different models
    print("\n" + "=" * 80)
    print("RANKING UNIVERSE CALCULATIONS")
    print("=" * 80)

    # Model A: Every AMFI scheme code
    model_a = len(schemes)

    # Model B: One underlying fund, retaining Direct/Regular separately
    model_b = len(fund_groups)

    # Model C: One underlying fund, Growth only
    model_c_count = 0
    for key, group in fund_groups.items():
        growth_schemes = [s for s in group if s["option"] == "Growth"]
        if growth_schemes:
            model_c_count += 1
        else:
            # Fallback to any option
            model_c_count += 1

    # Model D: One underlying fund, Direct Growth preferred
    model_d_count = 0
    model_d_direct_growth = 0
    model_d_direct_any = 0
    model_d_regular_growth = 0
    model_d_regular_any = 0
    model_d_any = 0

    for key, group in fund_groups.items():
        model_d_count += 1
        direct_growth = [s for s in group if s["plan"] == "Direct" and s["option"] == "Growth"]
        direct_any = [s for s in group if s["plan"] == "Direct"]
        regular_growth = [s for s in group if s["plan"] == "Regular" and s["option"] == "Growth"]
        regular_any = [s for s in group if s["plan"] == "Regular"]

        if direct_growth:
            model_d_direct_growth += 1
        elif direct_any:
            model_d_direct_any += 1
        elif regular_growth:
            model_d_regular_growth += 1
        elif regular_any:
            model_d_regular_any += 1
        else:
            model_d_any += 1

    # Model E: Direct Growth preferred with fallback
    model_e_count = len(fund_groups)

    print(f"\nModel A (Every AMFI scheme code): {model_a}")
    print(f"Model B (One underlying fund, Direct/Regular separate): {model_b}")
    print(f"Model C (One underlying fund, Growth only): {model_c_count}")
    print(f"Model D (One underlying fund, Direct Growth preferred): {model_d_count}")
    print(f"  - Direct Growth available: {model_d_direct_growth}")
    print(f"  - Direct (any option): {model_d_direct_any}")
    print(f"  - Regular Growth: {model_d_regular_growth}")
    print(f"  - Regular (any option): {model_d_regular_any}")
    print(f"  - Any available: {model_d_any}")
    print(f"Model E (Direct Growth with fallback): {model_e_count}")

    # Export detailed data
    output = {
        "total_schemes": len(schemes),
        "total_underlying_funds": len(fund_groups),
        "single_entry_funds": len(single_groups),
        "multi_entry_funds": len(multi_groups),
        "plan_distribution": dict(plan_dist),
        "option_distribution": dict(option_dist),
        "combo_distribution": {f"{k[0]}+{k[1]}": v for k, v in combo_dist.items()},
        "multi_entry_categories": {
            "complex": len(multi_complex),
            "direct_regular_only": len(multi_direct_regular),
            "growth_idcw_only": len(multi_both_options),
            "growth_only": len(multi_only_growth),
            "idcw_only": len(multi_only_idcw),
        },
        "ranking_universe": {
            "model_a_every_scheme": model_a,
            "model_b_underlying_fund": model_b,
            "model_c_growth_only": model_c_count,
            "model_d_direct_growth_preferred": model_d_count,
            "model_e_direct_growth_fallback": model_e_count,
        },
        "model_d_breakdown": {
            "direct_growth": model_d_direct_growth,
            "direct_any": model_d_direct_any,
            "regular_growth": model_d_regular_growth,
            "regular_any": model_d_regular_any,
            "any": model_d_any,
        },
        "inconsistent_categories": len(inconsistent_categories),
    }

    with open("/tmp/fund_identity_analysis.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDetailed analysis exported to /tmp/fund_identity_analysis.json")

    # Export examples for report
    examples = {
        "complex": [],
        "direct_regular_only": [],
        "growth_idcw_only": [],
    }

    for key, group in sorted(multi_complex, key=lambda x: -len(x[1]))[:15]:
        amc, fund_name = key.split("||")
        examples["complex"].append({
            "fund_name": fund_name,
            "amc": amc,
            "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"], "plan": s["plan"], "option": s["option"], "category": s["category"]} for s in group],
        })

    for key, group in sorted(multi_direct_regular, key=lambda x: -len(x[1]))[:10]:
        amc, fund_name = key.split("||")
        examples["direct_regular_only"].append({
            "fund_name": fund_name,
            "amc": amc,
            "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"], "plan": s["plan"], "option": s["option"], "category": s["category"]} for s in group],
        })

    for key, group in sorted(multi_both_options, key=lambda x: -len(x[1]))[:10]:
        amc, fund_name = key.split("||")
        examples["growth_idcw_only"].append({
            "fund_name": fund_name,
            "amc": amc,
            "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"], "plan": s["plan"], "option": s["option"], "category": s["category"]} for s in group],
        })

    with open("/tmp/fund_identity_examples.json", "w") as f:
        json.dump(examples, f, indent=2)

    print(f"Examples exported to /tmp/fund_identity_examples.json")


if __name__ == "__main__":
    asyncio.run(main())
