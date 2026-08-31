from unittest.mock import AsyncMock, patch

import pytest

from backend.config.settings import Settings
from backend.models.mutual_fund import MutualFund, NAVRecord, SchemeSearchResult
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.mutual_funds.normalizer import (
    normalize_nav_history,
    normalize_scheme,
    normalize_search_result,
)


@pytest.fixture
def fetcher():
    return MutualFundFetcher(settings=Settings())


def test_normalize_scheme_minimal():
    raw = {"scheme_code": "119594", "meta": {"scheme_name": "Test Fund"}}
    scheme = normalize_scheme(raw)
    assert scheme.scheme_code == "119594"
    assert scheme.scheme_name == "Test Fund"
    assert scheme.nav is None
    assert scheme.one_year_return is None


def test_normalize_scheme_full():
    raw = {
        "scheme_code": "119594",
        "meta": {
            "scheme_name": "Test Fund",
            "fund_house": "Test AMC",
            "scheme_category": "Equity",
            "scheme_type": "Large Cap",
            "scheme_nav": "100.50",
            "last_nav_date": "2024-12-31",
            "return_1year": "12.5",
            "return_3year": "15.0",
            "return_5year": "18.2",
            "expense_ratio": "1.2",
            "minimum_sip_amount": "500",
            "fund_manager": "Test Manager",
            "asset_allocation": {"equity": 80.0, "debt": 15.0, "cash": 5.0},
            "top_holdings": [{"stock": "TCS", "weight": 5.0}],
        },
    }
    scheme = normalize_scheme(raw)
    assert scheme.amc == "Test AMC"
    assert scheme.category == "Equity"
    assert scheme.nav == 100.50
    assert scheme.one_year_return == 12.5
    assert scheme.asset_allocation == {"equity": 80.0, "debt": 15.0, "cash": 5.0}


def test_normalize_scheme_invalid_nav():
    raw = {"scheme_code": "1", "meta": {"scheme_name": "Bad", "scheme_nav": "N/A"}}
    scheme = normalize_scheme(raw)
    assert scheme.nav is None


def test_normalize_nav_history():
    raw = {
        "data": [
            {"date": "2024-12-30", "nav": "100.0"},
            {"date": "2024-12-31", "nav": "101.5"},
            {"date": "2024-01-01", "nav": "invalid"},
        ]
    }
    records = normalize_nav_history(raw)
    assert len(records) == 2
    assert records[0].date == "2024-12-30"
    assert records[0].nav == 100.0
    assert records[1].nav == 101.5


def test_normalize_search_result():
    raw = {
        "scheme_code": "119594",
        "scheme_name": "Test Fund",
        "amc": "Test AMC",
        "category": "Equity",
        "sub_category": "Large Cap",
    }
    result = normalize_search_result(raw)
    assert result.scheme_code == "119594"
    assert result.category == "Equity"
    assert result.sub_category == "Large Cap"


def test_fetcher_get_scheme_caches(fetcher):
    import asyncio

    mock_raw = {
        "scheme_code": "119594",
        "meta": {"scheme_name": "Cached Fund", "scheme_nav": "50.0", "last_nav_date": "2024-12-31"},
    }
    with patch.object(fetcher.mfapi, "fetch_scheme", new_callable=AsyncMock, return_value=mock_raw):
        scheme1 = asyncio.run(fetcher.get_scheme("119594"))
        assert scheme1.scheme_name == "Cached Fund"
        scheme2 = asyncio.run(fetcher.get_scheme("119594"))
        assert scheme2.scheme_name == "Cached Fund"
        fetcher.mfapi.fetch_scheme.assert_called_once()


def test_fetcher_get_nav_history(fetcher):
    import asyncio

    mock_raw = {
        "data": [
            {"date": "2024-12-30", "nav": "100.0"},
            {"date": "2024-12-31", "nav": "101.0"},
        ]
    }

    # Mock TigZig as unavailable so it falls back to MFAPI
    with patch("backend.services.mutual_funds.fetcher.get_tigzig_dataset") as mock_tigzig:
        mock_tigzig.return_value.is_available = False
        with patch.object(fetcher.mfapi, "fetch_nav_history", new_callable=AsyncMock, return_value=mock_raw):
            records = asyncio.run(fetcher.get_nav_history("119594"))
            assert len(records) == 2
            assert records[0].nav == 100.0


def test_fetcher_search_schemes(fetcher):
    import asyncio

    mock_raw = [
        {"scheme_code": "1", "scheme_name": "Fund A", "amc": "AMC A", "category": "Equity"},
        {"scheme_code": "2", "scheme_name": "Fund B", "amc": "AMC B", "category": "Debt"},
    ]
    with patch.object(fetcher.mfapi, "search_schemes", new_callable=AsyncMock, return_value=mock_raw):
        results = asyncio.run(fetcher.search_schemes("test"))
        assert len(results) == 2
        assert results[0].scheme_name == "Fund A"


def test_fetcher_get_schemes_by_category(fetcher):
    import asyncio

    mock_raw = [
        {
            "scheme_code": "1",
            "meta": {
                "scheme_name": "Large Cap Fund",
                "scheme_category": "Equity Scheme - Large Cap Fund",
                "scheme_type": "Large Cap",
            },
        },
        {
            "scheme_code": "2",
            "meta": {
                "scheme_name": "Liquid Fund",
                "scheme_category": "Debt Scheme - Liquid Fund",
                "scheme_type": "Liquid",
            },
        },
    ]
    with patch.object(fetcher.mfapi, "fetch_scheme", new_callable=AsyncMock, return_value=mock_raw):
        # Test canonical category filtering
        large_cap = asyncio.run(fetcher.get_schemes_by_category("Equity - Large Cap"))
        assert len(large_cap) == 1
        assert large_cap[0].scheme_name == "Large Cap Fund"

        liquid = asyncio.run(fetcher.get_schemes_by_category("Debt - Liquid"))
        assert len(liquid) == 1
        assert liquid[0].scheme_name == "Liquid Fund"
