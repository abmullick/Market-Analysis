"""Deep dive into multi-entry fund groups.

Investigates what causes multiple AMFI scheme entries for the same underlying fund.
"""
import asyncio
import json
import re
import sys
from collections import defaultdict
from typing import Any

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

        schemes.append({
            "scheme_code": scheme_code,
            "scheme_name": scheme_name,
            "amc": current_amc,
            "category": current_category,
            "raw_parts": parts,
        })

    return schemes


def normalize_fund_name(scheme_name: str) -> str:
    """Extract the underlying fund name by removing plan/option suffixes."""
    name = scheme_name.strip()

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

    # Enrich with fund name
    for s in schemes:
        s["fund_name"] = normalize_fund_name(s["scheme_name"])

    # Group by AMC + fund_name
    fund_groups: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        key = f"{s['amc']}||{s['fund_name']}"
        fund_groups[key].append(s)

    multi_groups = {k: v for k, v in fund_groups.items() if len(v) > 1}

    print(f"Multi-entry funds: {len(multi_groups)}")

    # Analyze name patterns within multi-entry groups
    print("\n" + "=" * 80)
    print("NAME PATTERN ANALYSIS WITHIN MULTI-ENTRY GROUPS")
    print("=" * 80)

    # Categorize by name difference type
    identical_names = []
    suffix_only_diff = []
    other_diff = []

    for key, group in multi_groups.items():
        names = [s["scheme_name"] for s in group]
        unique_names = set(names)

        if len(unique_names) == 1:
            identical_names.append((key, group))
        else:
            # Check if names differ only by suffix
            base_names = set(normalize_fund_name(n) for n in unique_names)
            if len(base_names) == 1:
                suffix_only_diff.append((key, group))
            else:
                other_diff.append((key, group))

    print(f"\nIdentical names (same name, different codes): {len(identical_names)}")
    print(f"Suffix-only differences: {len(suffix_only_diff)}")
    print(f"Other name differences: {len(other_diff)}")

    # Show examples of identical names
    print("\n" + "=" * 80)
    print("EXAMPLE: Identical names, different scheme codes")
    print("=" * 80)

    for key, group in sorted(identical_names, key=lambda x: -len(x[1]))[:15]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        print(f"Category: {group[0]['category']}")
        for s in group:
            print(f"  [{s['scheme_code']}] {s['scheme_name']}")

    # Show examples of suffix-only differences
    print("\n" + "=" * 80)
    print("EXAMPLE: Suffix-only differences")
    print("=" * 80)

    for key, group in sorted(suffix_only_diff, key=lambda x: -len(x[1]))[:15]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        print(f"Category: {group[0]['category']}")
        for s in group:
            print(f"  [{s['scheme_code']}] {s['scheme_name']}")

    # Show examples of other differences
    print("\n" + "=" * 80)
    print("EXAMPLE: Other name differences")
    print("=" * 80)

    for key, group in sorted(other_diff, key=lambda x: -len(x[1]))[:15]:
        amc, fund_name = key.split("||")
        print(f"\nFund: {fund_name}")
        print(f"AMC: {amc}")
        print(f"Category: {group[0]['category']}")
        for s in group:
            print(f"  [{s['scheme_code']}] {s['scheme_name']}")

    # Analyze suffix patterns
    print("\n" + "=" * 80)
    print("SUFFIX PATTERN ANALYSIS")
    print("=" * 80)

    suffix_patterns = defaultdict(int)
    for key, group in suffix_only_diff:
        names = [s["scheme_name"] for s in group]
        base = normalize_fund_name(names[0])
        for name in names:
            suffix = name[len(base):].strip() if name.startswith(base) else name
            if suffix:
                suffix_patterns[suffix] += 1

    print("\nCommon suffix patterns:")
    for suffix, count in sorted(suffix_patterns.items(), key=lambda x: -x[1])[:20]:
        print(f"  '{suffix}': {count}")

    # Check for specific patterns
    print("\n" + "=" * 80)
    print("SPECIFIC PATTERN ANALYSIS")
    print("=" * 80)

    # Look for patterns like "Plan A", "Plan B", "Series 1", etc.
    plan_patterns = defaultdict(int)
    series_patterns = defaultdict(int)

    for key, group in multi_groups.items():
        for s in group:
            name = s["scheme_name"]
            # Plan patterns
            plan_match = re.search(r'\bPlan\s+([A-Z])\b', name)
            if plan_match:
                plan_patterns[f"Plan {plan_match.group(1)}"] += 1
            # Series patterns
            series_match = re.search(r'\bSeries\s+(\w+)\b', name)
            if series_match:
                series_patterns[f"Series {series_match.group(1)}"] += 1

    print("\nPlan patterns:")
    for pattern, count in sorted(plan_patterns.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")

    print("\nSeries patterns:")
    for pattern, count in sorted(series_patterns.items(), key=lambda x: -x[1])[:10]:
        print(f"  {pattern}: {count}")

    # Export comprehensive examples
    examples = {
        "identical_names": [],
        "suffix_only_diff": [],
        "other_diff": [],
    }

    for key, group in sorted(identical_names, key=lambda x: -len(x[1]))[:20]:
        amc, fund_name = key.split("||")
        examples["identical_names"].append({
            "fund_name": fund_name,
            "amc": amc,
            "category": group[0]["category"],
            "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"]} for s in group],
        })

    for key, group in sorted(suffix_only_diff, key=lambda x: -len(x[1]))[:20]:
        amc, fund_name = key.split("||")
        examples["suffix_only_diff"].append({
            "fund_name": fund_name,
            "amc": amc,
            "category": group[0]["category"],
            "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"]} for s in group],
        })

    for key, group in sorted(other_diff, key=lambda x: -len(x[1]))[:10]:
        amc, fund_name = key.split("||")
        examples["other_diff"].append({
            "fund_name": fund_name,
            "amc": amc,
            "category": group[0]["category"],
            "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"]} for s in group],
        })

    with open("/tmp/fund_identity_deep_analysis.json", "w") as f:
        json.dump(examples, f, indent=2)

    print(f"\nDeep analysis exported to /tmp/fund_identity_deep_analysis.json")


if __name__ == "__main__":
    asyncio.run(main())
