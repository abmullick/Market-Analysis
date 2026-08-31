"""Category normalization for AMFI mutual fund data.

This module provides functions to normalize and consolidate AMFI category names,
eliminating duplicates caused by naming inconsistencies in the source data.
"""
from typing import Any, Optional


# Mapping of raw AMFI category patterns to canonical category names
# This is ordered by specificity - more specific patterns should come first
CATEGORY_NORMALIZATION_RULES = [
    # Equity categories
    ("Equity Scheme - Contra Fund", "Equity - Contra"),
    ("Equity Schemes - Contra Fund", "Equity - Contra"),
    ("Equity Scheme - Dividend Yield Fund", "Equity - Dividend Yield"),
    ("Equity Schemes - Dividend Yield Fund", "Equity - Dividend Yield"),
    ("Equity Scheme - ELSS", "Equity - ELSS"),
    ("Equity Schemes - ELSS- Tax Saver Fund", "Equity - ELSS"),
    ("ELSS", "Equity - ELSS"),
    ("Equity Scheme - Flexi Cap Fund", "Equity - Flexi Cap"),
    ("Equity Schemes - Flexi Cap Fund", "Equity - Flexi Cap"),
    ("Equity Scheme - Focused Fund", "Equity - Focused"),
    ("Equity Schemes - Focused Fund", "Equity - Focused"),
    ("Equity Scheme - Large & Mid Cap Fund", "Equity - Large & Mid Cap"),
    ("Equity Schemes - Large & Mid Cap Fund", "Equity - Large & Mid Cap"),
    ("Equity Scheme - Large Cap Fund", "Equity - Large Cap"),
    ("Equity Schemes - Large Cap Fund", "Equity - Large Cap"),
    ("Equity Scheme - Mid Cap Fund", "Equity - Mid Cap"),
    ("Equity Schemes - Mid Cap Fund", "Equity - Mid Cap"),
    ("Equity Scheme - Multi Cap Fund", "Equity - Multi Cap"),
    ("Equity Schemes - Multi Cap Fund", "Equity - Multi Cap"),
    ("Equity Scheme - Sectoral/ Thematic", "Equity - Sectoral/Thematic"),
    ("Equity Schemes - Sectoral Fund", "Equity - Sectoral/Thematic"),
    ("Equity Schemes - Thematic Fund", "Equity - Sectoral/Thematic"),
    ("Equity Scheme - Small Cap Fund", "Equity - Small Cap"),
    ("Equity Schemes - Small Cap Fund", "Equity - Small Cap"),
    ("Equity Scheme - Value Fund", "Equity - Value"),
    ("Equity Schemes - Value Fund", "Equity - Value"),

    # Debt categories
    ("Debt Scheme - Banking and PSU Fund", "Debt - Banking & PSU"),
    ("Income/Debt Oriented Schemes - Banking and PSU Debt Fund", "Debt - Banking & PSU"),
    ("Debt Scheme - Corporate Bond Fund", "Debt - Corporate Bond"),
    ("Income/Debt Oriented Schemes - Corporate Bond Fund", "Debt - Corporate Bond"),
    ("Debt Scheme - Credit Risk Fund", "Debt - Credit Risk"),
    ("Income/Debt Oriented Schemes - Credit Risk Fund", "Debt - Credit Risk"),
    ("Debt Scheme - Dynamic Bond", "Debt - Dynamic Bond"),
    ("Debt Scheme - Floater Fund", "Debt - Floater"),
    ("Debt Scheme - Gilt Fund", "Debt - Gilt"),
    ("Gilt", "Debt - Gilt"),
    ("Income/Debt Oriented Schemes - Gilt Fund", "Debt - Gilt"),
    ("Income/Debt Oriented Schemes - 10-year Constant Maturity Gilt Fund", "Debt - 10Y Constant Maturity Gilt"),
    ("Debt Scheme - Liquid Fund", "Debt - Liquid"),
    ("Income/Debt Oriented Schemes - Liquid Fund", "Debt - Liquid"),
    ("Debt Scheme - Long Duration Fund", "Debt - Long Duration"),
    ("Debt Scheme - Low Duration Fund", "Debt - Low Duration"),
    ("Debt Scheme - Medium Duration Fund", "Debt - Medium Duration"),
    ("Debt Scheme - Medium to Long Duration Fund", "Debt - Medium to Long Duration"),
    ("Debt Scheme - Money Market Fund", "Debt - Money Market"),
    ("Money Market", "Debt - Money Market"),
    ("Income/Debt Oriented Schemes - Money Market Fund", "Debt - Money Market"),
    ("Debt Scheme - Overnight Fund", "Debt - Overnight"),
    ("Income/Debt Oriented Schemes - Overnight Fund", "Debt - Overnight"),
    ("Debt Scheme - Short Duration Fund", "Debt - Short Duration"),
    ("Income/Debt Oriented Schemes - Short Term Fund", "Debt - Short Duration"),
    ("Debt Scheme - Ultra Short Duration Fund", "Debt - Ultra Short Duration"),
    ("Income/Debt Oriented Schemes - Ultra Short Term Fund", "Debt - Ultra Short Duration"),
    ("Income/Debt Oriented Schemes - Ultra Short to Short Term Fund", "Debt - Ultra Short to Short Duration"),
    ("Income/Debt Oriented Schemes - Dynamic Term Fund", "Debt - Dynamic Term"),
    ("Income/Debt Oriented Schemes - Floating Interest Rates Fund", "Debt - Floating Rate"),
    ("Income/Debt Oriented Schemes - Long Term Fund", "Debt - Long Term"),
    ("Income/Debt Oriented Schemes - Medium Term Fund", "Debt - Medium Term"),
    ("Income/Debt Oriented Schemes - Medium to Long Term Fund", "Debt - Medium to Long Term"),
    ("Income/Debt Oriented Schemes - Fixed Term Plan", "Debt - Fixed Term Plan"),
    ("Income/Debt Oriented Schemes - Other Debt Scheme", "Debt - Other"),
    ("Income/Debt Oriented Schemes - Sectoral Fund", "Debt - Sectoral"),

    # Hybrid categories
    ("Hybrid Scheme - Aggressive Hybrid Fund", "Hybrid - Aggressive"),
    ("Hybrid Schemes - Aggressive Hybrid Fund", "Hybrid - Aggressive"),
    ("Hybrid Scheme - Arbitrage Fund", "Hybrid - Arbitrage"),
    ("Hybrid Schemes - Arbitrage Fund", "Hybrid - Arbitrage"),
    ("Hybrid Scheme - Balanced Hybrid Fund", "Hybrid - Balanced"),
    ("Hybrid Schemes - Balanced Hybrid Fund", "Hybrid - Balanced"),
    ("Hybrid Scheme - Conservative Hybrid Fund", "Hybrid - Conservative"),
    ("Hybrid Schemes - Conservative Hybrid Fund", "Hybrid - Conservative"),
    ("Hybrid Scheme - Dynamic Asset Allocation or Balanced Advantage", "Hybrid - Dynamic Asset Allocation"),
    ("Hybrid Schemes - Balanced Advantage Fund/ Dynamic Asset Allocation", "Hybrid - Dynamic Asset Allocation"),
    ("Hybrid Scheme - Equity Savings", "Hybrid - Equity Savings"),
    ("Hybrid Schemes - Equity Savings Fund", "Hybrid - Equity Savings"),
    ("Hybrid Scheme - Multi Asset Allocation", "Hybrid - Multi Asset Allocation"),
    ("Hybrid Schemes - Multi Asset Allocation Fund", "Hybrid - Multi Asset Allocation"),

    # Solution Oriented categories
    ("Solution Oriented Scheme - Children's Fund", "Solution Oriented - Children"),
    ("Solution Oriented Scheme - Retirement Fund", "Solution Oriented - Retirement"),
    ("Solution Oriented Schemes ** - Retirement Fund", "Solution Oriented - Retirement"),
    ("Children's Fund - Childrens' Fund", "Solution Oriented - Children"),

    # Other categories
    ("Exchange Traded Funds ", "Other - ETF"),
    ("Fund of Funds Scheme ", "Other - FoF Domestic"),
    ("Other Scheme - FoF Domestic", "Other - FoF Domestic"),
    ("Other Scheme - FoF Overseas", "Other - FoF Overseas"),
    ("Other Scheme - Gold ETF", "Other - Gold ETF"),
    ("Other Scheme - Index Funds", "Other - Index Funds"),
    ("Other Scheme - Other  ETFs", "Other - Other ETFs"),
    ("Index Funds - Debt Funds", "Other - Index Funds"),
    ("Index Funds - Equity Funds", "Other - Index Funds"),
    ("Index Funds - Hybrid Fund", "Other - Index Funds"),
    ("Overseas Fund of Funds - Fund of Funds investing overseas", "Other - FoF Overseas"),

    # Income/Growth (legacy categories - mostly ICICI Prudential)
    ("Income", "Other - Income"),
    ("Growth", "Other - Growth"),

    # Life Cycle
    ("Life Cycle Funds - Life Cycle Fund with Maturity of 10 Years", "Other - Life Cycle"),
    ("Life Cycle Funds - Life Cycle Fund with Maturity of 15 Years", "Other - Life Cycle"),
]


def normalize_category(raw_category: Optional[str]) -> str:
    """Normalize a raw AMFI category name to a canonical form.

    Args:
        raw_category: The raw category name from AMFI data

    Returns:
        A normalized canonical category name
    """
    if not raw_category:
        return "Unknown"

    # Strip whitespace
    cleaned = raw_category.strip()

    # Check against known patterns (exact match)
    for pattern, canonical in CATEGORY_NORMALIZATION_RULES:
        if cleaned == pattern.strip():
            return canonical

    # If no exact match, try case-insensitive match
    cleaned_lower = cleaned.lower()
    for pattern, canonical in CATEGORY_NORMALIZATION_RULES:
        if cleaned_lower == pattern.strip().lower():
            return canonical

    # If still no match, return a normalized version of the original
    # Remove common prefixes/suffixes
    result = cleaned_lower
    for prefix in [
        "equity scheme - ", "equity schemes - ",
        "debt scheme - ", "income/debt oriented schemes - ",
        "hybrid scheme - ", "hybrid schemes - ",
        "solution oriented scheme - ", "solution oriented schemes ** - ",
        "index funds - ", "other scheme - ",
        "fund of funds scheme - ", "overseas fund of funds - ",
    ]:
        if result.startswith(prefix):
            result = result[len(prefix):]
            break

    # Remove trailing punctuation and whitespace
    result = result.rstrip(" -_*").strip()

    # Normalize whitespace
    result = " ".join(result.split())

    return result if result else "Unknown"


def get_category_mapping() -> dict[str, str]:
    """Get a mapping of all raw category names to their canonical forms.

    Returns:
        Dictionary mapping raw category names to canonical names
    """
    mapping = {}
    for pattern, canonical in CATEGORY_NORMALIZATION_RULES:
        mapping[pattern] = canonical
    return mapping


class CategoryNormalizer:
    """Normalizes and consolidates AMFI category data."""

    def __init__(self):
        self._rules = CATEGORY_NORMALIZATION_RULES
        self._mapping = get_category_mapping()

    def normalize_scheme_category(self, raw_category: Optional[str]) -> str:
        """Normalize a scheme's category name.

        Args:
            raw_category: The raw category name from AMFI data

        Returns:
            The canonical category name
        """
        return normalize_category(raw_category)

    def get_canonical_categories(self) -> list[str]:
        """Get list of unique canonical category names.

        Returns:
            Sorted list of canonical category names
        """
        canonical = set()
        for _, canonical_name in self._rules:
            canonical.add(canonical_name)
        return sorted(canonical)

    def get_schemes_for_canonical_category(self, canonical_category: str) -> list[dict[str, Any]]:
        """Get all schemes belonging to a canonical category.

        Note: This is a placeholder that would need actual scheme data.
        In practice, this would query the database or cache.

        Args:
            canonical_category: The canonical category name

        Returns:
            List of scheme dictionaries
        """
        # This would be implemented with actual data source
        return []

    def get_total_raw_scheme_count(self) -> int:
        """Get total number of schemes in raw data.

        Returns:
            Total scheme count
        """
        # This would be implemented with actual data source
        return 0

    def get_total_canonical_scheme_count(self) -> int:
        """Get total number of schemes after normalization.

        Returns:
            Total scheme count (should equal raw count)
        """
        # This would be implemented with actual data source
        return 0
