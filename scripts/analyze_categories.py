"""Script to fetch and analyze MFAPI category data.

Fetches all schemes from MFAPI and builds a comprehensive category inventory.
"""
import asyncio
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")

from backend.config.settings import Settings
from backend.services.data.mfapi import MfapiClient


def parse_amfi_text(text: str) -> list[dict[str, Any]]:
    """Parse AMFI NAVAll.txt format into MFAPI-like structure."""
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
            "meta": {
                "scheme_name": scheme_name,
                "fund_house": current_amc,
                "scheme_category": current_category,
                "scheme_type": None,
            }
        })

    return schemes


async def main():
    settings = Settings()

    # Try MFAPI first
    from backend.services.data.mfapi import MfapiClient
    mfapi_client = MfapiClient(settings=settings)

    print("Fetching all schemes from MFAPI...")
    try:
        raw = await asyncio.wait_for(mfapi_client.fetch_scheme("all"), timeout=60.0)
        source = "MFAPI"
    except Exception as e:
        print(f"MFAPI failed: {e}")
        print("Falling back to AMFI...")
        from backend.services.data.amfi import AmfiClient
        amfi_client = AmfiClient(settings=settings)
        text = await amfi_client.fetch_nav_all()
        raw = parse_amfi_text(text)
        source = "AMFI"

    if not isinstance(raw, list):
        print(f"ERROR: Expected list, got {type(raw)}")
        return

    print(f"Source: {source}")
    print(f"Total schemes fetched: {len(raw)}")

    # Build category inventory
    category_schemes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    category_amcs: dict[str, set[str]] = defaultdict(set)
    schemes_without_category = []
    duplicate_codes = set()
    seen_codes = set()

    for item in raw:
        meta = item.get("meta", {})
        scheme_code = str(item.get("scheme_code", ""))
        scheme_name = meta.get("scheme_name", "")
        fund_house = meta.get("fund_house", "")
        scheme_category = meta.get("scheme_category", "")
        scheme_type = meta.get("scheme_type", "")

        # Check for duplicate codes
        if scheme_code in seen_codes:
            duplicate_codes.add(scheme_code)
        seen_codes.add(scheme_code)

        # Check for missing category
        if not scheme_category:
            schemes_without_category.append({
                "code": scheme_code,
                "name": scheme_name,
                "amc": fund_house,
                "type": scheme_type,
            })
            scheme_category = "(No Category)"

        category_schemes[scheme_category].append({
            "code": scheme_code,
            "name": scheme_name,
            "amc": fund_house,
            "type": scheme_type,
        })

        if fund_house:
            category_amcs[scheme_category].add(fund_house)

    # Print category inventory
    print("\n" + "=" * 80)
    print("CATEGORY INVENTORY")
    print("=" * 80)

    for category in sorted(category_schemes.keys()):
        schemes = category_schemes[category]
        amcs = category_amcs[category]
        print(f"\n--- {category} ---")
        print(f"  Schemes: {len(schemes)}")
        print(f"  AMCs: {len(amcs)}")
        print(f"  Example schemes:")
        for s in schemes[:3]:
            print(f"    - [{s['code']}] {s['name']} ({s['amc']})")

    # Print schemes without category
    if schemes_without_category:
        print(f"\n--- Schemes without category: {len(schemes_without_category)} ---")
        for s in schemes_without_category[:10]:
            print(f"  - [{s['code']}] {s['name']} ({s['amc']}) type={s['type']}")

    # Print duplicate codes
    if duplicate_codes:
        print(f"\n--- Duplicate scheme codes: {len(duplicate_codes)} ---")
        for code in sorted(duplicate_codes)[:10]:
            print(f"  - {code}")

    # Analyze category name variants
    print("\n" + "=" * 80)
    print("CATEGORY NAME VARIANT ANALYSIS")
    print("=" * 80)

    categories = list(category_schemes.keys())

    # Group by normalized name
    normalized_groups: dict[str, list[str]] = defaultdict(list)
    for cat in categories:
        normalized = cat.lower().strip()
        # Remove common suffixes/prefixes
        normalized = normalized.replace("scheme", "").replace("schemes", "")
        normalized = normalized.replace("fund", "").replace("funds", "")
        normalized = " ".join(normalized.split())  # normalize whitespace
        normalized_groups[normalized].append(cat)

    print("\nPotential duplicate categories (normalized name matches):")
    for normalized, variants in sorted(normalized_groups.items()):
        if len(variants) > 1:
            print(f"\n  Normalized: '{normalized}'")
            total_schemes = sum(len(category_schemes[v]) for v in variants)
            for v in variants:
                print(f"    - '{v}': {len(category_schemes[v])} schemes")

    # Analyze plan types (Direct vs Regular)
    print("\n" + "=" * 80)
    print("PLAN/OPTION ANALYSIS")
    print("=" * 80)

    plan_patterns = defaultdict(int)
    option_patterns = defaultdict(int)

    for category, schemes in category_schemes.items():
        for s in schemes:
            name = s["name"].lower()
            if "direct" in name:
                plan_patterns["Direct"] += 1
            elif "regular" in name:
                plan_patterns["Regular"] += 1
            else:
                plan_patterns["Unspecified"] += 1

            if "growth" in name:
                option_patterns["Growth"] += 1
            elif "idcw" in name or "dividend" in name:
                option_patterns["IDCW/Dividend"] += 1
            elif "reinves" in name:
                option_patterns["Reinvestment"] += 1
            else:
                option_patterns["Unspecified"] += 1

    print("\nPlan types across all schemes:")
    for plan, count in sorted(plan_patterns.items(), key=lambda x: -x[1]):
        print(f"  {plan}: {count}")

    print("\nOption types across all schemes:")
    for option, count in sorted(option_patterns.items(), key=lambda x: -x[1]):
        print(f"  {option}: {count}")

    # Check for funds with same base name but different plans/options
    print("\n" + "=" * 80)
    print("SAME FUND, MULTIPLE PLANS/OPTIONS")
    print("=" * 80)

    base_name_groups: dict[str, list[dict]] = defaultdict(list)
    for category, schemes in category_schemes.items():
        for s in schemes:
            name = s["name"]
            # Extract base name by removing plan/option suffixes
            base = name
            for suffix in [
                " - Direct Plan", " - Regular Plan",
                " - Direct", " - Regular",
                " - Growth", " - IDCW", " - Dividend",
                " Direct Plan", " Regular Plan",
                " Direct", " Regular",
                " Growth", " IDCW", " Dividend",
            ]:
                if base.endswith(suffix):
                    base = base[:-len(suffix)]
                    break
            base_name_groups[base].append(s)

    multi_plan_funds = {k: v for k, v in base_name_groups.items() if len(v) > 1}
    print(f"\nFunds with multiple plans/options: {len(multi_plan_funds)}")
    print("\nExamples:")
    for base, variants in sorted(multi_plan_funds.items())[:10]:
        print(f"\n  {base}:")
        for v in variants:
            print(f"    - [{v['code']}] {v['name']} ({v['amc']}) - Category: {next(cat for cat, schemes in category_schemes.items() if any(s['code'] == v['code'] for s in schemes))}")

    # Export full data for analysis
    print("\n" + "=" * 80)
    print("FULL CATEGORY DATA (JSON)")
    print("=" * 80)

    import json
    output = {
        "source": source,
        "total_schemes": len(raw),
        "total_categories": len(categories),
        "categories": {},
    }

    for category in sorted(categories):
        schemes = category_schemes[category]
        amcs = category_amcs[category]
        output["categories"][category] = {
            "scheme_count": len(schemes),
            "amc_count": len(amcs),
            "amcs": sorted(amcs),
            "schemes": [{"code": s["code"], "name": s["name"], "amc": s["amc"], "type": s["type"]} for s in schemes[:5]],
        }

    output_file = f"/tmp/mfapi_categories_{source.lower()}.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nFull data exported to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
