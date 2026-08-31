"""Script to analyze AMFI category duplicates and overlaps."""
import asyncio
import json
import sys
from collections import defaultdict
from typing import Any

sys.path.insert(0, "/home/abmul/projects/Market-Analysis")


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
    from backend.config.settings import Settings
    from backend.services.data.amfi import AmfiClient

    settings = Settings()
    amfi_client = AmfiClient(settings=settings)

    print("Fetching AMFI data...")
    text = await amfi_client.fetch_nav_all()
    raw = parse_amfi_text(text)

    print(f"Total schemes: {len(raw)}")

    # Build category -> schemes mapping
    category_schemes: dict[str, set[str]] = defaultdict(set)  # category -> set of scheme codes
    category_scheme_names: dict[str, list[str]] = defaultdict(list)
    scheme_to_categories: dict[str, set[str]] = defaultdict(set)  # scheme code -> categories

    for item in raw:
        meta = item.get("meta", {})
        scheme_code = str(item.get("scheme_code", ""))
        scheme_name = meta.get("scheme_name", "")
        scheme_category = meta.get("scheme_category", "")

        if scheme_category:
            category_schemes[scheme_category].add(scheme_code)
            category_scheme_names[scheme_category].append(scheme_name)
            scheme_to_categories[scheme_code].add(scheme_category)

    # Identify potential duplicate categories
    categories = list(category_schemes.keys())

    # Normalize category names for comparison
    def normalize_category(name: str) -> str:
        n = name.lower().strip()
        # Remove common prefixes/suffixes
        for prefix in ["equity scheme - ", "equity schemes - ", "debt scheme - ",
                       "hybrid scheme - ", "hybrid schemes - ", "income/debt oriented schemes - ",
                       "solution oriented scheme - ", "solution oriented schemes ** - ",
                       "index funds - ", "other scheme - ", "fund of funds scheme - ",
                       "overseas fund of funds - "]:
            if n.startswith(prefix):
                n = n[len(prefix):]
                break
        # Remove trailing punctuation and whitespace
        n = n.rstrip(" -_*").strip()
        # Normalize whitespace
        n = " ".join(n.split())
        return n

    normalized_groups: dict[str, list[str]] = defaultdict(list)
    for cat in categories:
        normalized = normalize_category(cat)
        normalized_groups[normalized].append(cat)

    # Find groups with multiple raw categories
    duplicate_groups = {k: v for k, v in normalized_groups.items() if len(v) > 1}

    print("\n" + "=" * 80)
    print("DUPLICATE CATEGORY GROUPS")
    print("=" * 80)

    for normalized, variants in sorted(duplicate_groups.items(), key=lambda x: -sum(len(category_schemes[v]) for v in x[1])):
        total_schemes = set()
        print(f"\nCanonical: '{normalized}'")
        for v in variants:
            schemes = category_schemes[v]
            total_schemes.update(schemes)
            print(f"  '{v}': {len(schemes)} schemes")
        print(f"  Total unique schemes: {len(total_schemes)}")

        # Check for overlapping schemes between variants
        if len(variants) == 2:
            set1 = category_schemes[variants[0]]
            set2 = category_schemes[variants[1]]
            overlap = set1 & set2
            if overlap:
                print(f"  WARNING: {len(overlap)} schemes appear in BOTH categories!")
            else:
                print(f"  No overlap - categories are disjoint")

    # Find schemes with multiple categories
    print("\n" + "=" * 80)
    print("SCHEMES WITH MULTIPLE CATEGORIES")
    print("=" * 80)

    multi_category = {k: v for k, v in scheme_to_categories.items() if len(v) > 1}
    print(f"\nSchemes appearing in multiple categories: {len(multi_category)}")

    for code, cats in sorted(multi_category.items())[:10]:
        names = [s["meta"]["scheme_name"] for s in raw if str(s["scheme_code"]) == code]
        name = names[0] if names else "Unknown"
        print(f"\n  [{code}] {name}:")
        for cat in cats:
            print(f"    - {cat}")

    # Plan/Option analysis
    print("\n" + "=" * 80)
    print("PLAN/OPTION ANALYSIS")
    print("=" * 80)

    # Group schemes by base name (without plan/option suffixes)
    base_name_groups: dict[str, list[dict]] = defaultdict(list)
    for item in raw:
        meta = item.get("meta", {})
        scheme_code = str(item.get("scheme_code", ""))
        scheme_name = meta.get("scheme_name", "")
        scheme_category = meta.get("scheme_category", "")

        # Extract base name
        base = scheme_name
        for suffix in [
            " - Direct Plan - Growth", " - Direct Plan - IDCW",
            " - Regular Plan - Growth", " - Regular Plan - IDCW",
            " - Direct - Growth", " - Direct - IDCW",
            " - Regular - Growth", " - Regular - IDCW",
            " - Direct Plan", " - Regular Plan",
            " Direct Plan", " Regular Plan",
            " - Growth", " - IDCW", " - Dividend",
            " Growth", " IDCW", " Dividend",
        ]:
            if base.endswith(suffix):
                base = base[:-len(suffix)].strip()
                break

        base_name_groups[base].append({
            "code": scheme_code,
            "name": scheme_name,
            "category": scheme_category,
        })

    # Find funds with multiple plans/options
    multi_option = {k: v for k, v in base_name_groups.items() if len(v) > 1}
    print(f"\nFunds with multiple plans/options: {len(multi_option)}")

    # Analyze plan types
    plan_types = defaultdict(int)
    option_types = defaultdict(int)
    for base, variants in multi_option.items():
        plans = set()
        options = set()
        for v in variants:
            name = v["name"]
            if "Direct" in name:
                plans.add("Direct")
            if "Regular" in name:
                plans.add("Regular")
            if "Growth" in name:
                options.add("Growth")
            if "IDCW" in name or "Dividend" in name:
                options.add("IDCW/Dividend")

        for p in plans:
            plan_types[p] += 1
        if not plans:
            plan_types["Unspecified"] += 1

        for o in options:
            option_types[o] += 1
        if not options:
            option_types["Unspecified"] += 1

    print("\nPlan types in multi-option funds:")
    for plan, count in sorted(plan_types.items(), key=lambda x: -x[1]):
        print(f"  {plan}: {count}")

    print("\nOption types in multi-option funds:")
    for option, count in sorted(option_types.items(), key=lambda x: -x[1]):
        print(f"  {option}: {count}")

    # Category summary
    print("\n" + "=" * 80)
    print("CATEGORY SUMMARY (sorted by scheme count)")
    print("=" * 80)

    for cat in sorted(categories, key=lambda c: -len(category_schemes[c])):
        print(f"{len(category_schemes[cat]):5d} | {cat}")

    # Export detailed analysis
    output = {
        "total_schemes": len(raw),
        "total_categories": len(categories),
        "duplicate_groups": {
            normalized: {
                "variants": variants,
                "scheme_counts": {v: len(category_schemes[v]) for v in variants},
                "total_unique": len(set().union(*[category_schemes[v] for v in variants])),
            }
            for normalized, variants in sorted(duplicate_groups.items(), key=lambda x: -sum(len(category_schemes[v]) for v in x[1]))
        },
        "schemes_with_multiple_categories": len(multi_category),
        "multi_option_funds": len(multi_option),
        "categories": {
            cat: len(category_schemes[cat])
            for cat in sorted(categories, key=lambda c: -len(category_schemes[c]))
        },
    }

    with open("/tmp/amfi_category_analysis.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDetailed analysis exported to /tmp/amfi_category_analysis.json")


if __name__ == "__main__":
    asyncio.run(main())
