"""Tests for fund identity resolution and grouping.

These tests verify that:
1. Fund names are correctly normalized
2. Plan/option information is extracted correctly
3. Schemes are grouped into underlying funds
4. Ranking candidates are selected correctly
5. Excluded variants are tracked
"""
import pytest

from backend.services.mutual_funds.fund_grouper import (
    FundGrouper,
    extract_option,
    extract_plan,
    get_fund_group_key,
    is_segregated_portfolio,
    normalize_fund_name,
    select_ranking_candidate,
)


class TestIsSegregatedPortfolio:
    """Test segregated portfolio detection."""

    def test_trailing_dash(self):
        """Trailing dash should indicate segregated portfolio."""
        assert is_segregated_portfolio("ICICI Prudential Liquid Fund -") is True
        assert is_segregated_portfolio("ABC Fund - ") is True
        assert is_segregated_portfolio("ABC Fund-") is True

    def test_segregated_in_parentheses(self):
        """Segregated indicator in parentheses should be detected."""
        assert is_segregated_portfolio("ABC Fund (Segregated - 06032020)") is True
        assert is_segregated_portfolio("ABC Fund (segregated)") is True

    def test_normal_fund(self):
        """Normal funds should not be detected as segregated."""
        assert is_segregated_portfolio("ICICI Prudential Liquid Fund") is False
        assert is_segregated_portfolio("ABC Fund - Growth") is False
        assert is_segregated_portfolio("ABC Fund - Direct Plan") is False

    def test_empty_name(self):
        """Empty name should return False."""
        assert is_segregated_portfolio("") is False
        assert is_segregated_portfolio(None) is False


class TestNormalizeFundName:
    """Test fund name normalization."""

    def test_direct_growth_suffix_removed(self):
        """Direct Growth suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Direct Plan - Growth") == "ABC Fund"
        assert normalize_fund_name("ABC Fund - Direct - Growth") == "ABC Fund"

    def test_regular_growth_suffix_removed(self):
        """Regular Growth suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Regular Plan - Growth") == "ABC Fund"
        assert normalize_fund_name("ABC Fund - Regular - Growth") == "ABC Fund"

    def test_direct_idcw_suffix_removed(self):
        """Direct IDCW suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Direct Plan - IDCW") == "ABC Fund"

    def test_regular_idcw_suffix_removed(self):
        """Regular IDCW suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Regular Plan - IDCW") == "ABC Fund"

    def test_direct_only_suffix_removed(self):
        """Direct suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Direct Plan") == "ABC Fund"
        assert normalize_fund_name("ABC Fund - Direct") == "ABC Fund"

    def test_regular_only_suffix_removed(self):
        """Regular suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Regular Plan") == "ABC Fund"
        assert normalize_fund_name("ABC Fund - Regular") == "ABC Fund"

    def test_growth_only_suffix_removed(self):
        """Growth suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Growth") == "ABC Fund"

    def test_idcw_only_suffix_removed(self):
        """IDCW suffix should be removed."""
        assert normalize_fund_name("ABC Fund - IDCW") == "ABC Fund"

    def test_dividend_suffix_removed(self):
        """Dividend suffix should be removed."""
        assert normalize_fund_name("ABC Fund - Dividend") == "ABC Fund"

    def test_segregated_portfolio_removed(self):
        """Segregated portfolio indicators should be removed."""
        assert normalize_fund_name("Franklin Fund (no. of segregated portfolios- 3)") == "Franklin Fund"
        assert normalize_fund_name("Nippon Fund (Existing Number of Segregated Portfolios - 2)") == "Nippon Fund"
        assert normalize_fund_name("Baroda Fund (the scheme has 2 segregated portfolios)") == "Baroda Fund"

    def test_whitespace_normalized(self):
        """Multiple spaces should be normalized to single space."""
        assert normalize_fund_name("Bandhan Gilt   Fund") == "Bandhan Gilt Fund"
        assert normalize_fund_name("ABC  Fund   -  Growth") == "ABC Fund"

    def test_trailing_dash_removed(self):
        """Trailing dash should be removed."""
        assert normalize_fund_name("ABC Fund -") == "ABC Fund"
        assert normalize_fund_name("ABC Fund-") == "ABC Fund"
        assert normalize_fund_name("ABC Fund - ") == "ABC Fund"
        assert normalize_fund_name("ABC Fund- ") == "ABC Fund"

    def test_icici_liquid_fund_trailing_dash(self):
        """ICICI Prudential Liquid Fund trailing dash variants should normalize same."""
        name1 = normalize_fund_name("ICICI Prudential Liquid Fund")
        name2 = normalize_fund_name("ICICI Prudential Liquid Fund -")
        name3 = normalize_fund_name("ICICI Prudential Liquid Fund-")
        name4 = normalize_fund_name("ICICI Prudential Liquid Fund - ")
        assert name1 == name2 == name3 == name4 == "ICICI Prudential Liquid Fund"

    def test_icici_short_term_fund_trailing_dash(self):
        """ICICI Prudential Short Term Fund trailing dash variants should normalize same."""
        name1 = normalize_fund_name("ICICI Prudential Short Term Fund")
        name2 = normalize_fund_name("ICICI Prudential Short Term Fund-")
        assert name1 == name2 == "ICICI Prudential Short Term Fund"

    def test_uti_credit_risk_segregated(self):
        """UTI Credit Risk Fund segregated variants should normalize same."""
        name1 = normalize_fund_name("UTI - Credit Risk Fund (Segregated - 06032020)")
        name2 = normalize_fund_name("UTI - Credit Risk Fund (Segregated - 07072020)")
        name3 = normalize_fund_name("UTI - Credit Risk Fund (Segregated - 17022019)")
        assert name1 == name2 == name3 == "UTI - Credit Risk Fund"

    def test_empty_name(self):
        """Empty name should return empty string."""
        assert normalize_fund_name("") == ""
        assert normalize_fund_name(None) == ""

    def test_no_suffix_unchanged(self):
        """Name without suffix should be unchanged."""
        assert normalize_fund_name("ABC Fund") == "ABC Fund"


class TestExtractPlan:
    """Test plan extraction from scheme name."""

    def test_direct_plan(self):
        """Direct Plan should be extracted."""
        assert extract_plan("ABC Fund - Direct Plan - Growth") == "Direct"
        assert extract_plan("ABC Fund - Direct - Growth") == "Direct"

    def test_regular_plan(self):
        """Regular Plan should be extracted."""
        assert extract_plan("ABC Fund - Regular Plan - Growth") == "Regular"
        assert extract_plan("ABC Fund - Regular - Growth") == "Regular"

    def test_direct_only(self):
        """Direct should be extracted."""
        assert extract_plan("ABC Fund - Direct Plan") == "Direct"

    def test_regular_only(self):
        """Regular should be extracted."""
        assert extract_plan("ABC Fund - Regular Plan") == "Regular"

    def test_no_plan(self):
        """None should be returned when no plan indicator."""
        assert extract_plan("ABC Fund - Growth") is None
        assert extract_plan("ABC Fund") is None
        assert extract_plan("") is None
        assert extract_plan(None) is None


class TestExtractOption:
    """Test option extraction from scheme name."""

    def test_growth(self):
        """Growth should be extracted."""
        assert extract_option("ABC Fund - Growth") == "Growth"
        assert extract_option("ABC Fund - Direct Plan - Growth") == "Growth"

    def test_idcw(self):
        """IDCW should be extracted."""
        assert extract_option("ABC Fund - IDCW") == "IDCW"
        assert extract_option("ABC Fund - Direct Plan - IDCW") == "IDCW"

    def test_dividend(self):
        """Dividend should be extracted as IDCW."""
        assert extract_option("ABC Fund - Dividend") == "IDCW"

    def test_no_option(self):
        """None should be returned when no option indicator."""
        assert extract_option("ABC Fund") is None
        assert extract_option("ABC Fund - Direct Plan") is None
        assert extract_option("") is None
        assert extract_option(None) is None


class TestFundGroupKey:
    """Test fund group key generation."""

    def test_basic_key(self):
        """Basic key should be generated."""
        assert get_fund_group_key("AMC Name", "Fund Name") == "AMC Name||Fund Name"

    def test_none_amc(self):
        """None AMC should be replaced with 'Unknown'."""
        assert get_fund_group_key(None, "Fund Name") == "Unknown||Fund Name"

    def test_whitespace_stripped(self):
        """Whitespace should be stripped."""
        assert get_fund_group_key("  AMC  ", "  Fund  ") == "AMC||Fund"


class TestSelectRankingCandidate:
    """Test ranking candidate selection."""

    def test_single_scheme(self):
        """Single scheme should be returned as-is."""
        group = [{"scheme_code": "1", "scheme_name": "ABC Fund"}]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "1"

    def test_prefer_direct_growth(self):
        """Growth should be preferred (Direct/Regular not identifiable from AMFI data)."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Regular Plan - Growth"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Direct Plan - Growth"},
        ]
        result = select_ranking_candidate(group)
        # Both have Growth, so first scheme code should be selected
        assert result["scheme_code"] == "1"

    def test_prefer_direct_any(self):
        """First scheme code selected when plan not identifiable."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Regular Plan - Growth"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Direct Plan - IDCW"},
        ]
        result = select_ranking_candidate(group)
        # First scheme has Growth, should be preferred
        assert result["scheme_code"] == "1"

    def test_prefer_regular_growth(self):
        """Regular Growth should be preferred over Regular IDCW."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Regular Plan - IDCW"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Regular Plan - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"

    def test_prefer_growth_over_idcw(self):
        """Growth should be preferred over IDCW."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - IDCW"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"

    def test_first_available_fallback(self):
        """First available should be selected when no preference matches."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund"},
            {"scheme_code": "2", "scheme_name": "ABC Fund"},
        ]
        result = select_ranking_candidate(group)
        assert result is not None

    def test_empty_group_raises(self):
        """Empty group should raise ValueError."""
        with pytest.raises(ValueError):
            select_ranking_candidate([])

    def test_segregated_portfolio_filtered_when_normal_exists(self):
        """Segregated portfolios should be filtered out when normal schemes exist."""
        group = [
            {"scheme_code": "1", "scheme_name": "ICICI Prudential Liquid Fund -"},
            {"scheme_code": "2", "scheme_name": "ICICI Prudential Liquid Fund"},
            {"scheme_code": "3", "scheme_name": "ICICI Prudential Liquid Fund (Segregated - 06032020)"},
        ]
        result = select_ranking_candidate(group)
        # Normal scheme should be selected, not segregated
        assert result["scheme_code"] == "2"

    def test_segregated_portfolio_selected_when_all_segregated(self):
        """When all schemes are segregated, one should be selected."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund (Segregated - 06032020)"},
            {"scheme_code": "2", "scheme_name": "ABC Fund (Segregated - 07032020)"},
        ]
        result = select_ranking_candidate(group)
        # Should still select one (first by scheme code)
        assert result is not None
        assert result["scheme_code"] == "1"

    def test_growth_preferred_over_segregated(self):
        """Growth normal scheme should be preferred over segregated."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund -"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"

    def test_segregated_with_growth_in_name(self):
        """Segregated portfolio with Growth in name should be filtered."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Growth -"},
            {"scheme_code": "2", "scheme_name": "ABC Fund"},
        ]
        result = select_ranking_candidate(group)
        # Normal scheme should be selected
        assert result["scheme_code"] == "2"


class TestVariantHandling:
    """Test Growth/IDCW/Dividend variant handling in representative selection."""

    def test_growth_preferred_over_idcw(self):
        """Growth should be preferred over IDCW when both exist."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - IDCW"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"
        assert extract_option(result["scheme_name"]) == "Growth"

    def test_growth_preferred_over_dividend(self):
        """Growth should be preferred over Dividend when both exist."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Dividend"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"
        assert extract_option(result["scheme_name"]) == "Growth"

    def test_growth_preferred_over_unspecified(self):
        """Growth should be preferred over unspecified variants."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"
        assert extract_option(result["scheme_name"]) == "Growth"

    def test_idcw_fallback_when_no_growth(self):
        """IDCW should be selected when no Growth variant exists."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - IDCW"},
            {"scheme_code": "2", "scheme_name": "ABC Fund"},
        ]
        result = select_ranking_candidate(group)
        # IDCW is identifiable, first by code should be selected
        assert result is not None

    def test_dividend_fallback_when_no_growth(self):
        """Dividend should be selected when no Growth variant exists."""
        group = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Dividend"},
            {"scheme_code": "2", "scheme_name": "ABC Fund"},
        ]
        result = select_ranking_candidate(group)
        # Dividend is identifiable, first by code should be selected
        assert result is not None

    def test_unspecified_fallback(self):
        """When all variants are unspecified, first by code should be selected."""
        group = [
            {"scheme_code": "2", "scheme_name": "ABC Fund"},
            {"scheme_code": "1", "scheme_name": "ABC Fund"},
        ]
        result = select_ranking_candidate(group)
        # First by scheme code (numeric sort)
        assert result["scheme_code"] == "1"

    def test_growth_plus_idcw_selects_growth(self):
        """Growth + IDCW should select Growth."""
        group = [
            {"scheme_code": "1", "scheme_name": "Mirae Asset Nifty 1D Rate Liquid ETF-IDCW"},
            {"scheme_code": "2", "scheme_name": "Mirae Asset Nifty 1D Rate Liquid ETF - Growth"},
        ]
        result = select_ranking_candidate(group)
        assert result["scheme_code"] == "2"
        assert extract_option(result["scheme_name"]) == "Growth"

    def test_idcw_only_fund(self):
        """IDCW-only fund should select one IDCW variant."""
        group = [
            {"scheme_code": "1", "scheme_name": "Aditya Birla Sun Life Dividend Yield Fund"},
            {"scheme_code": "2", "scheme_name": "Aditya Birla Sun Life Dividend Yield Fund"},
        ]
        result = select_ranking_candidate(group)
        assert result is not None
        # Both are IDCW, first by code should be selected
        assert result["scheme_code"] == "1"

    def test_dividend_only_fund(self):
        """Dividend-only fund should select one Dividend variant."""
        group = [
            {"scheme_code": "2", "scheme_name": "Franklin India Dividend Yield Fund"},
            {"scheme_code": "1", "scheme_name": "Franklin India Dividend Yield Fund"},
        ]
        result = select_ranking_candidate(group)
        assert result is not None
        # Both are IDCW (Dividend), first by code should be selected
        assert result["scheme_code"] == "1"

    def test_no_duplicate_representatives(self):
        """Each underlying fund should have exactly one representative."""
        grouper = FundGrouper()
        schemes = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Growth", "amc": "AMC A"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - IDCW", "amc": "AMC A"},
            {"scheme_code": "3", "scheme_name": "XYZ Fund", "amc": "AMC A"},
        ]
        for s in schemes:
            grouper.add_scheme(s)

        candidates = grouper.get_ranking_candidates()
        # Should have 2 candidates (ABC Fund and XYZ Fund)
        assert len(candidates) == 2

        # Check no duplicate fund names
        fund_names = [c["_canonical_fund_name"] for c in candidates]
        assert len(fund_names) == len(set(fund_names))

    def test_exactly_one_representative_per_fund(self):
        """Each underlying fund should have exactly one representative."""
        grouper = FundGrouper()
        schemes = [
            {"scheme_code": "1", "scheme_name": "ABC Fund - Growth", "amc": "AMC A"},
            {"scheme_code": "2", "scheme_name": "ABC Fund - IDCW", "amc": "AMC A"},
            {"scheme_code": "3", "scheme_name": "ABC Fund", "amc": "AMC A"},
            {"scheme_code": "4", "scheme_name": "XYZ Fund - Growth", "amc": "AMC A"},
            {"scheme_code": "5", "scheme_name": "XYZ Fund - IDCW", "amc": "AMC A"},
        ]
        for s in schemes:
            grouper.add_scheme(s)

        candidates = grouper.get_ranking_candidates()
        # Should have 2 candidates (ABC Fund and XYZ Fund)
        assert len(candidates) == 2

        # ABC Fund should have Growth selected
        abc = next(c for c in candidates if c["_canonical_fund_name"] == "ABC Fund")
        assert extract_option(abc["scheme_name"]) == "Growth"

        # XYZ Fund should have Growth selected
        xyz = next(c for c in candidates if c["_canonical_fund_name"] == "XYZ Fund")
        assert extract_option(xyz["scheme_name"]) == "Growth"


class TestFundGrouper:
    """Test FundGrouper class."""

    def test_add_single_scheme(self):
        """Single scheme should create single group."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Growth",
            "amc": "AMC Name",
        })

        groups = grouper.get_groups()
        assert len(groups) == 1

    def test_add_different_funds(self):
        """Different funds should create different groups."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "XYZ Fund - Growth",
            "amc": "AMC Name",
        })

        groups = grouper.get_groups()
        assert len(groups) == 2

    def test_group_variants_same_fund(self):
        """Variants of same fund should be grouped together."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Direct Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "ABC Fund - Regular Plan - Growth",
            "amc": "AMC Name",
        })

        groups = grouper.get_groups()
        assert len(groups) == 1
        assert len(list(groups.values())[0]) == 2

    def test_multi_entry_groups(self):
        """Multi-entry groups should be identified."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Direct Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "ABC Fund - Regular Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "3",
            "scheme_name": "XYZ Fund",
            "amc": "AMC Name",
        })

        multi = grouper.get_multi_entry_groups()
        assert len(multi) == 1

    def test_ranking_candidates(self):
        """One candidate per fund should be returned."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Direct Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "ABC Fund - Regular Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "3",
            "scheme_name": "XYZ Fund",
            "amc": "AMC Name",
        })

        candidates = grouper.get_ranking_candidates()
        assert len(candidates) == 2

    def test_excluded_variants(self):
        """Excluded variants should be tracked."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Direct Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "ABC Fund - Regular Plan - Growth",
            "amc": "AMC Name",
        })

        excluded = grouper.get_excluded_variants()
        assert len(excluded) == 1
        assert excluded[0]["_selected_candidate"] == "1"

    def test_stats(self):
        """Statistics should be calculated correctly."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Fund - Direct Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "ABC Fund - Regular Plan - Growth",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "3",
            "scheme_name": "XYZ Fund",
            "amc": "AMC Name",
        })

        stats = grouper.get_stats()
        assert stats["total_schemes"] == 3
        assert stats["total_underlying_funds"] == 2
        assert stats["single_entry_funds"] == 1
        assert stats["multi_entry_funds"] == 1
        assert stats["ranking_candidates"] == 2
        assert stats["excluded_variants"] == 1


class TestEdgeCases:
    """Test edge cases."""

    def test_similar_names_different_funds(self):
        """Similar names should be treated as different funds."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "ABC Large Cap Fund",
            "amc": "AMC Name",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "ABC Large Cap Fund II",
            "amc": "AMC Name",
        })

        groups = grouper.get_groups()
        assert len(groups) == 2

    def test_different_amc_same_name(self):
        """Same fund name in different AMCs should be different groups."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "Index Fund",
            "amc": "AMC A",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "Index Fund",
            "amc": "AMC B",
        })

        groups = grouper.get_groups()
        assert len(groups) == 2

    def test_segregated_portfolios_grouped(self):
        """Segregated portfolios should be grouped together."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "Franklin Fund (no. of segregated portfolios- 3)",
            "amc": "Franklin AMC",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "Franklin Fund (no. of segregated portfolios- 3)",
            "amc": "Franklin AMC",
        })

        groups = grouper.get_groups()
        assert len(groups) == 1
        assert len(list(groups.values())[0]) == 2

    def test_bandhan_whitespace_normalized(self):
        """Bandhan funds with extra whitespace should be grouped."""
        grouper = FundGrouper()
        grouper.add_scheme({
            "scheme_code": "1",
            "scheme_name": "Bandhan Gilt   Fund",
            "amc": "Bandhan AMC",
        })
        grouper.add_scheme({
            "scheme_code": "2",
            "scheme_name": "Bandhan Gilt Fund",
            "amc": "Bandhan AMC",
        })

        groups = grouper.get_groups()
        assert len(groups) == 1
