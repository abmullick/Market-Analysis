"""Fund identity resolution for AMFI mutual fund data.

This module provides functions to group multiple AMFI scheme entries
into underlying funds and select a single ranking candidate per fund.
"""
import re
from typing import Any, Optional


def normalize_fund_name(scheme_name: str) -> str:
    """Extract the underlying fund name by removing plan/option suffixes.

    This function removes common suffixes that indicate different plans
    (Direct/Regular) or options (Growth/IDCW/Dividend) to identify
    the underlying fund.

    Args:
        scheme_name: The raw scheme name from AMFI data

    Returns:
        Normalized fund name
    """
    if not scheme_name:
        return ""

    name = scheme_name.strip()

    # Remove common suffixes in order of specificity (most specific first)
    suffixes = [
        # Plan + Option combinations
        r'\s*-\s*Direct Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Regular Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Direct\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Regular\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Regular Plan\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Direct\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s+Regular\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        # Plan only
        r'\s*-\s*Direct Plan\s*$',
        r'\s*-\s*Regular Plan\s*$',
        r'\s*-\s*Direct\s*$',
        r'\s*-\s*Regular\s*$',
        r'\s+Direct Plan\s*$',
        r'\s+Regular Plan\s*$',
        r'\s+Direct\s*$',
        r'\s+Regular\s*$',
        # Option only
        r'\s*-\s*(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        r'\s*-\s*Dividend\s*$',
        r'\s+(Growth|IDCW|Dividend|Payout|Reinvestment)\s*$',
        # Segregated portfolio indicators
        r'\s*\(.*?segregated.*?\)\s*$',
        r'\(.*?no\.?\s*of\s*segregated.*?\)\s*$',
        r'\(.*?Existing\s*(Number|number)\s*of\s*Segregated.*?\)\s*$',
        r'\(.*?the\s*scheme\s*has.*?\)\s*$',
        # Trailing dash with optional whitespace (must be after other patterns)
        r'\s*-\s*$',
    ]

    for suffix in suffixes:
        match = re.search(suffix, name, re.IGNORECASE)
        if match:
            name = name[:match.start()]
            break

    # Clean up whitespace and trailing punctuation
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    name = name.rstrip(' -_')
    name = name.strip()

    return name


def extract_plan(scheme_name: str) -> Optional[str]:
    """Extract plan type from scheme name.

    Args:
        scheme_name: The raw scheme name

    Returns:
        'Direct', 'Regular', or None
    """
    if not scheme_name:
        return None

    name = scheme_name.strip()

    # Check for Direct/Regular indicators
    if re.search(r'\bDirect Plan\b', name, re.IGNORECASE):
        return "Direct"
    if re.search(r'\bDirect\b', name, re.IGNORECASE):
        return "Direct"
    if re.search(r'\bRegular Plan\b', name, re.IGNORECASE):
        return "Regular"
    if re.search(r'\bRegular\b', name, re.IGNORECASE):
        return "Regular"

    return None


def extract_option(scheme_name: str) -> Optional[str]:
    """Extract option type from scheme name.

    Args:
        scheme_name: The raw scheme name

    Returns:
        'Growth', 'IDCW', or None
    """
    if not scheme_name:
        return None

    name = scheme_name.strip()

    # Check for option indicators
    if re.search(r'\bGrowth\b', name, re.IGNORECASE):
        return "Growth"
    if re.search(r'\bIDCW\b', name, re.IGNORECASE):
        return "IDCW"
    if re.search(r'\bDividend\b', name, re.IGNORECASE):
        return "IDCW"
    if re.search(r'\bPayout\b', name, re.IGNORECASE):
        return "IDCW"
    if re.search(r'\bReinvestment\b', name, re.IGNORECASE):
        return "IDCW"

    return None


def get_fund_group_key(amc: Optional[str], fund_name: str) -> str:
    """Generate a unique key for grouping schemes into underlying funds.

    Args:
        amc: The AMC name
        fund_name: The normalized fund name

    Returns:
        A unique key string
    """
    amc_clean = (amc or "Unknown").strip()
    fund_clean = (fund_name or "Unknown").strip()
    return f"{amc_clean}||{fund_clean}"


def select_ranking_candidate(group: list[dict[str, Any]]) -> dict[str, Any]:
    """Select a single ranking candidate from a group of scheme variants.

    Selection hierarchy:
    1. Growth (when Growth/IDCW can be identified from scheme name)
    2. First scheme code (sorted numerically) as deterministic fallback

    IMPORTANT LIMITATION:
    AMFI NAVAll.txt does NOT reliably encode Direct/Regular plan information.
    Therefore, this function does NOT attempt to prefer Direct over Regular.
    The selected scheme may be either Direct or Regular - we simply don't know.

    Args:
        group: List of scheme dictionaries with 'scheme_name' key

    Returns:
        The selected scheme dictionary
    """
    if not group:
        raise ValueError("Cannot select from empty group")

    if len(group) == 1:
        return group[0]

    # Enrich with option info
    enriched = []
    for s in group:
        enriched.append({
            **s,
            "option": extract_option(s.get("scheme_name", "")),
        })

    # Selection hierarchy
    # 1. Prefer Growth when identifiable
    for s in enriched:
        if s["option"] == "Growth":
            return s

    # 2. Deterministic fallback: first scheme code sorted numerically
    sorted_group = sorted(group, key=lambda x: int(x["scheme_code"]))
    return sorted_group[0]


class FundGrouper:
    """Groups AMFI schemes into underlying funds."""

    def __init__(self):
        self._groups: dict[str, list[dict[str, Any]]] = {}

    def add_scheme(self, scheme: dict[str, Any]) -> None:
        """Add a scheme to the appropriate fund group.

        Args:
            scheme: Scheme dictionary with 'amc', 'scheme_name' keys
        """
        amc = scheme.get("amc")
        fund_name = normalize_fund_name(scheme.get("scheme_name", ""))
        key = get_fund_group_key(amc, fund_name)

        if key not in self._groups:
            self._groups[key] = []
        self._groups[key].append(scheme)

    def get_groups(self) -> dict[str, list[dict[str, Any]]]:
        """Get all fund groups.

        Returns:
            Dictionary mapping group keys to lists of schemes
        """
        return self._groups

    def get_multi_entry_groups(self) -> dict[str, list[dict[str, Any]]]:
        """Get only groups with multiple entries.

        Returns:
            Dictionary of multi-entry groups
        """
        return {k: v for k, v in self._groups.items() if len(v) > 1}

    def get_ranking_candidates(self) -> list[dict[str, Any]]:
        """Get one ranking candidate per underlying fund.

        Returns:
            List of selected scheme dictionaries with traceability fields
        """
        candidates = []
        for key, group in self._groups.items():
            candidate = select_ranking_candidate(group)
            # Add traceability fields
            candidate["_underlying_fund_id"] = key
            candidate["_amc"] = candidate.get("amc")
            candidate["_canonical_fund_name"] = key.split("||")[1] if "||" in key else ""
            candidate["_canonical_category"] = candidate.get("category")
            candidate["_representative_scheme_code"] = candidate["scheme_code"]
            candidate["_all_scheme_codes"] = [s["scheme_code"] for s in group]
            candidate["_group_size"] = len(group)
            candidate["_excluded_variants"] = [
                s["scheme_code"] for s in group if s["scheme_code"] != candidate["scheme_code"]
            ]
            candidates.append(candidate)
        return candidates

    def get_excluded_variants(self) -> list[dict[str, Any]]:
        """Get all excluded plan/option variants.

        Returns:
            List of excluded scheme dictionaries
        """
        excluded = []
        for key, group in self._groups.items():
            if len(group) <= 1:
                continue
            candidate = select_ranking_candidate(group)
            candidate_code = candidate["scheme_code"]
            for s in group:
                if s["scheme_code"] != candidate_code:
                    s_copy = {**s, "_excluded_reason": "variant", "_selected_candidate": candidate_code}
                    excluded.append(s_copy)
        return excluded

    def get_stats(self) -> dict[str, Any]:
        """Get grouping statistics.

        Returns:
            Dictionary with statistics
        """
        total_schemes = sum(len(g) for g in self._groups.values())
        multi_entry = self.get_multi_entry_groups()
        single_entry_count = len(self._groups) - len(multi_entry)

        return {
            "total_schemes": total_schemes,
            "total_underlying_funds": len(self._groups),
            "single_entry_funds": single_entry_count,
            "multi_entry_funds": len(multi_entry),
            "ranking_candidates": len(self._groups),
            "excluded_variants": total_schemes - len(self._groups),
        }
