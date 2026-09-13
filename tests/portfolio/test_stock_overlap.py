"""Minimal tests for stock overlap & concentration logic."""
import pytest

from backend.services.portfolio.stock_overlap import compute_stock_overlap


def _holding(code, isin, name, weight):
    return {"scheme_code": code, "isin": isin, "security_name": name,
            "portfolio_weight": weight}


def test_two_funds_share_a_stock():
    funds = [{"scheme_code": "A", "scheme_name": "Fund A", "allocation": 60},
             {"scheme_code": "B", "scheme_name": "Fund B", "allocation": 40}]
    holdings = [_holding("A", "INE001", "HDFC Bank Ltd.", 10.0),
                _holding("B", "INE001", "HDFC Bank Ltd.", 6.0)]
    result = compute_stock_overlap(funds, holdings)
    assert result["overlapping_stock_count"] == 1
    assert result["total_unique_stock_count"] == 1
    (stock,) = result["stocks"]
    assert stock["isin"] == "INE001"
    assert stock["fund_count"] == 2
    assert stock["effective_portfolio_exposure"] == pytest.approx(8.4)
    by_code = {f["scheme_code"]: f for f in stock["funds"]}
    assert by_code["A"]["effective_exposure"] == pytest.approx(6.0)
    assert by_code["B"]["effective_exposure"] == pytest.approx(2.4)


def test_same_isin_different_names_is_one_stock():
    funds = [{"scheme_code": "A", "scheme_name": "Fund A", "allocation": 50},
             {"scheme_code": "B", "scheme_name": "Fund B", "allocation": 50}]
    holdings = [_holding("A", "INE002", "HDFC Bank", 8.0),
                _holding("B", "INE002", "HDFC Bank Limited", 4.0)]
    result = compute_stock_overlap(funds, holdings)
    assert result["total_unique_stock_count"] == 1
    assert result["overlapping_stock_count"] == 1
    (stock,) = result["stocks"]
    assert stock["fund_count"] == 2
    assert stock["effective_portfolio_exposure"] == 4.0 + 2.0


def test_duplicate_isin_within_one_fund_is_added_first():
    funds = [{"scheme_code": "A", "scheme_name": "Fund A", "allocation": 60}]
    holdings = [_holding("A", "INE003", "Stock X", 4.0),
                _holding("A", "INE003", "Stock X", 6.0)]
    result = compute_stock_overlap(funds, holdings)
    assert result["total_unique_stock_count"] == 1
    assert result["overlapping_stock_count"] == 0
    (stock,) = result["stocks"]
    assert stock["fund_count"] == 1
    (entry,) = stock["funds"]
    assert entry["holding_weight"] == 10.0
    assert entry["effective_exposure"] == 6.0
    assert stock["effective_portfolio_exposure"] == 6.0
