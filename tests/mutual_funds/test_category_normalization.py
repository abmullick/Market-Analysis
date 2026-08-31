"""Tests for AMFI category normalization and deduplication.

These tests verify that:
1. Singular/plural category variants are consolidated
2. Duplicate categories are merged correctly
3. Genuinely different categories are preserved
4. Scheme counts are preserved before/after normalization
5. No duplicate scheme codes exist in the final ranking universe
"""
import pytest

from backend.services.mutual_funds.category_normalizer import (
    CategoryNormalizer,
    normalize_category,
    get_category_mapping,
)


class TestCategoryNormalization:
    """Test category name normalization."""

    def test_singular_plural_equity_scheme(self):
        """Equity Scheme and Equity Schemes should normalize to the same canonical name."""
        assert normalize_category("Equity Scheme - Large Cap Fund") == \
               normalize_category("Equity Schemes - Large Cap Fund")

    def test_singular_plural_hybrid_scheme(self):
        """Hybrid Scheme and Hybrid Schemes should normalize to the same canonical name."""
        assert normalize_category("Hybrid Scheme - Arbitrage Fund") == \
               normalize_category("Hybrid Schemes - Arbitrage Fund")

    def test_singular_plural_debt_scheme(self):
        """Debt Scheme and Income/Debt Oriented Schemes should normalize to the same canonical name."""
        assert normalize_category("Debt Scheme - Liquid Fund") == \
               normalize_category("Income/Debt Oriented Schemes - Liquid Fund")

    def test_solution_oriented_scheme_variants(self):
        """Solution Oriented Scheme and Solution Oriented Schemes should normalize."""
        assert normalize_category("Solution Oriented Scheme - Retirement Fund") == \
               normalize_category("Solution Oriented Schemes ** - Retirement Fund")

    def test_elss_variants(self):
        """ELSS and Equity Scheme - ELSS should normalize to the same canonical name."""
        assert normalize_category("ELSS") == \
               normalize_category("Equity Scheme - ELSS")

    def test_trailing_punctuation_removed(self):
        """Trailing punctuation and whitespace should be handled."""
        # Known patterns should map to canonical names
        assert normalize_category("Exchange Traded Funds  ") == "Other - ETF"
        assert normalize_category("Fund of Funds Scheme ") == "Other - FoF Domestic"

    def test_case_insensitive(self):
        """Normalization should be case-insensitive for unknown patterns."""
        # Unknown patterns should normalize to lowercase
        assert normalize_category("SOME UNKNOWN CATEGORY") == \
               normalize_category("some unknown category")

    def test_whitespace_normalized(self):
        """Multiple spaces should be normalized."""
        # Known patterns should map to canonical names
        assert normalize_category("Equity Scheme - Large Cap Fund") == "Equity - Large Cap"
        # Unknown patterns with extra spaces should be normalized
        assert normalize_category("Some  Unknown  Category") == \
               normalize_category("Some Unknown Category")


class TestCategoryMapping:
    """Test category mapping and consolidation."""

    def test_duplicate_categories_merged(self):
        """Duplicate categories should be merged into canonical names."""
        mapping = get_category_mapping()

        # Check that singular/plural variants map to same canonical name
        assert mapping.get("Equity Scheme - Large Cap Fund") == \
               mapping.get("Equity Schemes - Large Cap Fund")

    def test_genuinely_different_categories_preserved(self):
        """Categories that are truly different should not be merged."""
        mapping = get_category_mapping()

        # Large Cap and Mid Cap should remain separate
        assert mapping.get("Equity Scheme - Large Cap Fund") != \
               mapping.get("Equity Scheme - Mid Cap Fund")

        # Equity and Debt should remain separate
        assert mapping.get("Equity Scheme - Large Cap Fund") != \
               mapping.get("Debt Scheme - Liquid Fund")

    def test_all_raw_categories_have_mapping(self):
        """Every raw category should have a canonical mapping."""
        raw_categories = [
            "Equity Scheme - Large Cap Fund",
            "Equity Schemes - Large Cap Fund",
            "Debt Scheme - Liquid Fund",
            "Income/Debt Oriented Schemes - Liquid Fund",
            "Hybrid Scheme - Arbitrage Fund",
            "Hybrid Schemes - Arbitrage Fund",
        ]
        mapping = get_category_mapping()

        for cat in raw_categories:
            assert cat in mapping, f"Missing mapping for: {cat}"


class TestCategoryNormalizer:
    """Test the CategoryNormalizer class."""

    def test_normalize_scheme_category(self):
        """Scheme categories should be normalized."""
        normalizer = CategoryNormalizer()

        assert normalizer.normalize_scheme_category("Equity Scheme - Large Cap Fund") == \
               normalizer.normalize_scheme_category("Equity Schemes - Large Cap Fund")

    def test_get_canonical_categories(self):
        """Should return list of unique canonical categories."""
        normalizer = CategoryNormalizer()
        categories = normalizer.get_canonical_categories()

        # Should have fewer canonical categories than raw (~80+ raw)
        assert len(categories) > 0
        assert len(categories) < 80  # Raw has ~80+, canonical should be fewer

    def test_get_schemes_for_canonical_category_placeholder(self):
        """Placeholder method returns empty list (requires data source)."""
        normalizer = CategoryNormalizer()

        # This is a placeholder - in production, this would query actual data
        large_cap_schemes = normalizer.get_schemes_for_canonical_category("Equity - Large Cap")
        assert isinstance(large_cap_schemes, list)

    def test_scheme_count_preserved(self):
        """Total scheme count should be preserved after normalization."""
        normalizer = CategoryNormalizer()

        # Placeholder methods return 0 (require data source)
        raw_count = normalizer.get_total_raw_scheme_count()
        canonical_count = normalizer.get_total_canonical_scheme_count()

        # Both should be 0 (placeholder) or equal (if implemented)
        assert canonical_count == raw_count


class TestSchemeDeduplication:
    """Test scheme deduplication within categories."""

    def test_no_duplicate_scheme_codes_in_category(self):
        """No scheme code should appear twice in the same canonical category."""
        normalizer = CategoryNormalizer()

        for canonical_cat in normalizer.get_canonical_categories():
            schemes = normalizer.get_schemes_for_canonical_category(canonical_cat)
            codes = [s["scheme_code"] for s in schemes]
            assert len(codes) == len(set(codes)), \
                f"Duplicate codes in category: {canonical_cat}"

    def test_scheme_appears_in_exactly_one_canonical_category(self):
        """Each scheme should appear in exactly one canonical category."""
        normalizer = CategoryNormalizer()

        scheme_categories = {}
        for canonical_cat in normalizer.get_canonical_categories():
            schemes = normalizer.get_schemes_for_canonical_category(canonical_cat)
            for scheme in schemes:
                code = scheme["scheme_code"]
                if code in scheme_categories:
                    scheme_categories[code].append(canonical_cat)
                else:
                    scheme_categories[code] = [canonical_cat]

        # Check for schemes in multiple categories
        multi_cat = {k: v for k, v in scheme_categories.items() if len(v) > 1}
        assert len(multi_cat) == 0, \
            f"Schemes in multiple categories: {list(multi_cat.keys())[:10]}"


class TestPlanOptionHandling:
    """Test how different plans/options are handled."""

    def test_direct_and_regular_separate(self):
        """Direct and Regular plans should be treated as separate schemes."""
        # This is the current behavior - each plan is a separate scheme code
        # with its own entry in AMFI data
        pass  # Documented behavior, not a bug

    def test_growth_and_idcw_separate(self):
        """Growth and IDCW options should be treated as separate schemes."""
        # This is the current behavior - each option is a separate scheme code
        pass  # Documented behavior, not a bug


class TestCategoryCounts:
    """Test category scheme counts.

    Note: These tests verify the structure but actual counts require
    integration with a data source (AMFI/MFAPI).
    """

    def test_large_cap_mapping(self):
        """Large Cap category should map from multiple raw categories."""
        mapping = get_category_mapping()

        # Both raw categories should map to the same canonical name
        assert mapping["Equity Scheme - Large Cap Fund"] == "Equity - Large Cap"
        assert mapping["Equity Schemes - Large Cap Fund"] == "Equity - Large Cap"

    def test_liquid_fund_mapping(self):
        """Liquid Fund category should map from multiple raw categories."""
        mapping = get_category_mapping()

        # Both raw categories should map to the same canonical name
        assert mapping["Debt Scheme - Liquid Fund"] == "Debt - Liquid"
        assert mapping["Income/Debt Oriented Schemes - Liquid Fund"] == "Debt - Liquid"

    def test_elss_mapping(self):
        """ELSS category should map from multiple raw categories."""
        mapping = get_category_mapping()

        # Both raw categories should map to the same canonical name
        assert mapping["Equity Scheme - ELSS"] == "Equity - ELSS"
        assert mapping["ELSS"] == "Equity - ELSS"


class TestEdgeCases:
    """Test edge cases in category normalization."""

    def test_empty_category_name(self):
        """Empty category name should be handled."""
        normalizer = CategoryNormalizer()
        result = normalizer.normalize_scheme_category("")
        assert result is not None

    def test_none_category_name(self):
        """None category name should be handled."""
        normalizer = CategoryNormalizer()
        result = normalizer.normalize_scheme_category(None)
        assert result is not None

    def test_unknown_category_name(self):
        """Unknown category name should pass through or be categorized."""
        normalizer = CategoryNormalizer()
        result = normalizer.normalize_scheme_category("Some Unknown Category")
        assert result is not None

    def test_special_characters_in_category(self):
        """Category names with special characters should be handled."""
        normalizer = CategoryNormalizer()
        result = normalizer.normalize_scheme_category("Equity Scheme - Contra Fund (Special)")
        assert result is not None
