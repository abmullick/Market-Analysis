"""Final validation of the proposed fund grouping algorithm.

Validates that AMC + normalized name grouping does not incorrectly merge
genuinely different funds.
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

        # Extract ISIN if available
        isin = None
        if len(parts) > 4:
            potential_isin = parts[4].strip()
            if re.match(r'^[A-Z]{2}[A-Z0-9]{9}\d$', potential_isin):
                isin = potential_isin
        if len(parts) > 5 and not isin:
            potential_isin = parts[5].strip()
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


def normalize_fund_name(scheme_name: str) -> str:
    """Extract the underlying fund name by removing plan/option suffixes."""
    if not scheme_name:
        return ""

    name = scheme_name.strip()

    suffixes = [
        r'\s*-\s*Direct Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Regular Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Direct\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Regular\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Regular Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Regular\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Direct Plan\s*$',
        r'\s*-\s*Regular Plan\s*$',
        r'\s*-\s*Direct\s*$',
        r'\s*-\s*Regular\s*$',
        r'\s+Direct Plan\s*$',
        r'\s+Regular Plan\s*$',
        r'\s+Direct\s*$',
        r'\s+Regular\s*$',
        r'\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Dividend\s*$',
        r'\s+(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*\(.*?segregated.*?\)\s*$',
        r'\(.*?no\.?\s*of\s*segregated.*?\)\s*$',
        r'\(.*?Existing\s*(Number|number)\s*of\s*Segregated.*?\)\s*$',
        r'\(.*?the\s*scheme\s*has.*?\)\s*$',
    ]

    for suffix in suffixes:
        match = re.search(suffix, name, re.IGNORECASE)
        if match:
            name = name[:match.start()]
            break

    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    name = name.rstrip(' -_')

    return name


def is_segregated_portfolio(scheme_name: str) -> bool:
    """Check if scheme name indicates a segregated portfolio."""
    patterns = [
        r'segregated',
        r'no\.?\s*of\s*portfolio',
        r'existing\s*number',
        r'the\s*scheme\s*has',
    ]
    for pattern in patterns:
        if re.search(pattern, scheme_name, re.IGNORECASE):
            return True
    return False


def classify_group(group: list[dict]) -> dict[str, Any]:
    """Classify a group of schemes to determine if grouping is correct."""
    names = [s["scheme_name"] for s in group]
    categories = set(s["category"] for s in group)
    isins = set(s["isin"] for s in group if s["isin"])
    amc = group[0]["amc"]

    # Check for segregated portfolios
    segregated_count = sum(1 for n in names if is_segregated_portfolio(n))
    all_segregated = segregated_count == len(names)

    # Check name similarity
    base_names = set(normalize_fund_name(n) for n in names)
    unique_original_names = set(names)

    # Check for material name differences
    name_diffs = []
    if len(unique_original_names) > 1:
        name_list = list(unique_original_names)
        for i in range(len(name_list)):
            for j in range(i + 1, len(name_list)):
                diff = name_list[j][len(name_list[i]):] if name_list[j].startswith(name_list[i]) else name_list[j]
                name_diffs.append((name_list[i], name_list[j], diff))

    # Determine risk classification
    risk = "LOW"
    reasons = []

    if len(categories) > 1:
        risk = "HIGH"
        reasons.append("Multiple categories")

    if len(isins) > 1:
        risk = "MEDIUM"
        reasons.append("Multiple ISINs")

    if len(unique_original_names) > 1 and not all_segregated:
        # Check if names differ materially (not just whitespace/suffix)
        base_without_suffix = set()
        for n in unique_original_names:
            # Remove common suffixes for comparison
            cleaned = re.sub(r'\s*-\s*(Growth|IDCW|Dividend)\s*$', '', n, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            base_without_suffix.add(cleaned)

        if len(base_without_suffix) > 1:
            risk = "HIGH"
            reasons.append("Materially different names")
        else:
            risk = "LOW"
            reasons.append("Only suffix differences")

    if all_segregated:
        risk = "LOW"
        reasons.append("All segregated portfolios")

    return {
        "risk": risk,
        "reasons": reasons,
        "segregated_count": segregated_count,
        "all_segregated": all_segregated,
        "unique_names": len(unique_original_names),
        "unique_isins": len(isins),
        "categories": list(categories),
        "name_diffs": name_diffs,
    }


async def main():
    from backend.config.settings import Settings
    from backend.services.data.amfi import AmfiClient

    settings = Settings()
    amfi_client = AmfiClient(settings=settings)

    print("Fetching AMFI data...")
    text = await amfi_client.fetch_nav_all()
    schemes = parse_amfi_text(text)

    print(f"Total schemes: {len(schemes)}")

    # Group by AMC + normalized name
    fund_groups: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        fund_name = normalize_fund_name(s["scheme_name"])
        key = f"{s['amc']}||{fund_name}"
        fund_groups[key].append(s)

    multi_groups = {k: v for k, v in fund_groups.items() if len(v) > 1}

    print(f"Multi-entry groups: {len(multi_groups)}")

    # 1. FALSE MERGE ANALYSIS - 100 largest groups
    print("\n" + "=" * 80)
    print("1. FALSE MERGE ANALYSIS - 100 LARGEST GROUPS")
    print("=" * 80)

    largest_groups = sorted(multi_groups.items(), key=lambda x: -len(x[1]))[:100]

    risk_summary = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    high_risk_groups = []

    for key, group in largest_groups:
        amc, fund_name = key.split("||")
        classification = classify_group(group)
        risk_summary[classification["risk"]] += 1

        if classification["risk"] in ("HIGH", "MEDIUM"):
            high_risk_groups.append({
                "key": key,
                "amc": amc,
                "fund_name": fund_name,
                "group_size": len(group),
                "classification": classification,
                "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"], "category": s["category"], "isin": s["isin"]} for s in group[:5]],
            })

    print(f"\nRisk distribution (100 largest groups):")
    for risk, count in risk_summary.items():
        print(f"  {risk}: {count}")

    print(f"\nHigh/Medium risk groups: {len(high_risk_groups)}")
    for g in high_risk_groups[:20]:
        print(f"\n  {g['fund_name']} ({g['amc']})")
        print(f"    Risk: {g['classification']['risk']}")
        print(f"    Reasons: {g['classification']['reasons']}")
        print(f"    Schemes: {g['group_size']}")
        for s in g["schemes"][:3]:
            print(f"      [{s['code']}] {s['name'][:60]}")

    # 2. NORMALIZED NAME COLLISIONS
    print("\n" + "=" * 80)
    print("2. NORMALIZED NAME COLLISIONS")
    print("=" * 80)

    collisions = []
    for key, group in multi_groups.items():
        unique_names = set(s["scheme_name"] for s in group)
        if len(unique_names) > 1:
            # Check if names differ materially
            base_names = set(normalize_fund_name(n) for n in unique_names)
            if len(base_names) == 1:
                # Names normalize to same value but differ originally
                amc, fund_name = key.split("||")
                collisions.append({
                    "amc": amc,
                    "normalized_name": fund_name,
                    "original_names": list(unique_names),
                    "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"]} for s in group],
                })

    print(f"\nTotal collisions: {len(collisions)}")

    # Categorize collisions
    whitespace_only = []
    suffix_only = []
    material_diff = []

    for c in collisions:
        names = c["original_names"]
        # Check if only whitespace differs
        whitespace_normalized = set(re.sub(r'\s+', ' ', n).strip() for n in names)
        if len(whitespace_normalized) == 1:
            whitespace_only.append(c)
            continue

        # Check if only suffix differs
        suffix_stripped = set()
        for n in names:
            cleaned = re.sub(r'\s*-\s*(Growth|IDCW|Dividend|Direct|Regular|Plan)\s*$', '', n, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            suffix_stripped.add(cleaned)
        if len(suffix_stripped) == 1:
            suffix_only.append(c)
            continue

        material_diff.append(c)

    print(f"  Whitespace only: {len(whitespace_only)}")
    print(f"  Suffix only: {len(suffix_only)}")
    print(f"  Material difference: {len(material_diff)}")

    print(f"\nMaterial difference collisions (potential false merges):")
    for c in material_diff[:20]:
        print(f"\n  {c['normalized_name']} ({c['amc']})")
        for s in c["schemes"]:
            print(f"    [{s['code']}] {s['name']}")

    # 3. SAME NAME / DIFFERENT FUND
    print("\n" + "=" * 80)
    print("3. SAME NAME / DIFFERENT FUND ANALYSIS")
    print("=" * 80)

    # Find schemes with identical names but different AMCs
    name_amc_groups: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        name_amc_groups[s["scheme_name"]].append(s)

    same_name_diff_amc = {k: v for k, v in name_amc_groups.items() if len(set(s["amc"] for s in v)) > 1}
    print(f"\nSame name, different AMCs: {len(same_name_diff_amc)}")

    # Find schemes with same AMC + same name but different categories
    same_name_same_amc: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        key = f"{s['amc']}||{s['scheme_name']}"
        same_name_same_amc[key].append(s)

    same_name_multi = {k: v for k, v in same_name_same_amc.items() if len(v) > 1}
    print(f"Same AMC + same name, multiple codes: {len(same_name_multi)}")

    # 4. SEGREGATED PORTFOLIOS
    print("\n" + "=" * 80)
    print("4. SEGREGATED PORTFOLIO ANALYSIS")
    print("=" * 80)

    segregated_groups = []
    non_segregated_multi = []

    for key, group in multi_groups.items():
        all_segregated = all(is_segregated_portfolio(s["scheme_name"]) for s in group)
        if all_segregated:
            segregated_groups.append((key, group))
        else:
            non_segregated_multi.append((key, group))

    print(f"\nGroups with all segregated portfolios: {len(segregated_groups)}")
    print(f"Groups with non-segregated entries: {len(non_segregated_multi)}")

    # Analyze non-segregated multi-entry groups
    print(f"\nNon-segregated multi-entry groups breakdown:")
    category_consistent = 0
    category_inconsistent = 0

    for key, group in non_segregated_multi:
        categories = set(s["category"] for s in group)
        if len(categories) == 1:
            category_consistent += 1
        else:
            category_inconsistent += 1

    print(f"  Category consistent: {category_consistent}")
    print(f"  Category inconsistent: {category_inconsistent}")

    # 5. CATEGORY CONSISTENCY
    print("\n" + "=" * 80)
    print("5. CATEGORY CONSISTENCY CHECK")
    print("=" * 80)

    inconsistent_groups = []
    for key, group in multi_groups.items():
        categories = set(s["category"] for s in group)
        if len(categories) > 1:
            inconsistent_groups.append({
                "key": key,
                "amc": group[0]["amc"],
                "fund_name": key.split("||")[1],
                "categories": list(categories),
                "schemes": [{"code": s["scheme_code"], "name": s["scheme_name"], "category": s["category"]} for s in group],
            })

    print(f"\nGroups with inconsistent categories: {len(inconsistent_groups)}")

    for g in inconsistent_groups[:10]:
        print(f"\n  {g['fund_name']} ({g['amc']})")
        print(f"    Categories: {g['categories']}")
        for s in g["schemes"]:
            print(f"      [{s['code']}] {s['name'][:50]} -> {s['category']}")

    # 6. ALTERNATIVE IDENTIFIERS
    print("\n" + "=" * 80)
    print("6. ALTERNATIVE IDENTIFIERS COMPARISON")
    print("=" * 80)

    # Model A: AMC + normalized name
    model_a = fund_groups

    # Model B: AMC + normalized name + ISIN
    model_b_groups: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        fund_name = normalize_fund_name(s["scheme_name"])
        isin = s["isin"] or "NO_ISIN"
        key = f"{s['amc']}||{fund_name}||{isin}"
        model_b_groups[key].append(s)

    # Model C: AMC + normalized name + category
    model_c_groups: dict[str, list[dict]] = defaultdict(list)
    for s in schemes:
        fund_name = normalize_fund_name(s["scheme_name"])
        category = s["category"] or "NO_CATEGORY"
        key = f"{s['amc']}||{fund_name}||{category}"
        model_c_groups[key].append(s)

    print(f"\nModel A (AMC + normalized name): {len(model_a)} groups")
    print(f"Model B (AMC + name + ISIN): {len(model_b_groups)} groups")
    print(f"Model C (AMC + name + category): {len(model_c_groups)} groups")

    # Count multi-entry groups for each
    model_a_multi = sum(1 for g in model_a.values() if len(g) > 1)
    model_b_multi = sum(1 for g in model_b_groups.values() if len(g) > 1)
    model_c_multi = sum(1 for g in model_c_groups.values() if len(g) > 1)

    print(f"\nMulti-entry groups:")
    print(f"  Model A: {model_a_multi}")
    print(f"  Model B: {model_b_multi}")
    print(f"  Model C: {model_c_multi}")

    # ISIN coverage
    schemes_with_isin = sum(1 for s in schemes if s["isin"])
    print(f"\nISIN coverage: {schemes_with_isin}/{len(schemes)} ({schemes_with_isin/len(schemes)*100:.1f}%)")

    # 7. FINAL VERDICT
    print("\n" + "=" * 80)
    print("7. FINAL VERDICT")
    print("=" * 80)

    total_multi = len(multi_groups)
    high_risk = len([g for g in high_risk_groups if g["classification"]["risk"] == "HIGH"])
    material_collisions = len(material_diff)
    category_issues = len(inconsistent_groups)

    print(f"\nSummary:")
    print(f"  Total multi-entry groups: {total_multi}")
    print(f"  High risk groups: {high_risk}")
    print(f"  Material name collisions: {material_collisions}")
    print(f"  Category inconsistencies: {category_issues}")

    # Determine verdict
    issues = high_risk + material_collisions + category_issues
    if issues == 0:
        verdict = "SAFE TO IMPLEMENT"
        reason = "No false merge risks detected"
    elif issues < 10:
        verdict = "SAFE TO IMPLEMENT WITH MONITORING"
        reason = f"Only {issues} potential issues detected, all edge cases"
    else:
        verdict = "NEEDS MORE WORK"
        reason = f"{issues} potential issues require resolution"

    print(f"\nVerdict: {verdict}")
    print(f"Reason: {reason}")

    # Export comprehensive results
    output = {
        "summary": {
            "total_schemes": len(schemes),
            "total_groups": len(fund_groups),
            "multi_entry_groups": len(multi_groups),
            "single_entry_groups": len(fund_groups) - len(multi_groups),
        },
        "false_merge_analysis": {
            "largest_groups_analyzed": 100,
            "risk_distribution": risk_summary,
            "high_risk_count": len(high_risk_groups),
            "high_risk_examples": high_risk_groups[:10],
        },
        "name_collisions": {
            "total": len(collisions),
            "whitespace_only": len(whitespace_only),
            "suffix_only": len(suffix_only),
            "material_difference": len(material_diff),
            "material_examples": material_diff[:10],
        },
        "segregated_portfolios": {
            "all_segregated_groups": len(segregated_groups),
            "non_segregated_groups": len(non_segregated_multi),
            "category_consistent": category_consistent,
            "category_inconsistent": category_inconsistent,
        },
        "category_consistency": {
            "inconsistent_groups": len(inconsistent_groups),
            "examples": inconsistent_groups[:10],
        },
        "alternative_identifiers": {
            "model_a_groups": len(model_a),
            "model_b_groups": len(model_b_groups),
            "model_c_groups": len(model_c_groups),
            "isin_coverage_pct": schemes_with_isin / len(schemes) * 100,
        },
        "verdict": {
            "decision": verdict,
            "reason": reason,
            "issues_count": issues,
        },
    }

    with open("/tmp/fund_grouping_validation.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nDetailed results exported to /tmp/fund_grouping_validation.json")


if __name__ == "__main__":
    asyncio.run(main())
