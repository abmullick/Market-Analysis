"""Compact validation helpers for stock AI insight requests.

The AI layer only interprets deterministic stock-analysis data already produced
by the application. It does not calculate financial metrics or rankings.
"""
from __future__ import annotations

from typing import Any


REQUIRED_INDIVIDUAL_KEYS = {"analysis_type", "selected_stock"}
REQUIRED_COMPARISON_KEYS = {"analysis_type", "stocks"}


def _ensure_dict(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def validate_stock_insight_context(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _ensure_dict(payload, "Stock AI context")
    if payload.get("analysis_type") != "individual_stock":
        raise ValueError("Invalid stock AI analysis type")
    if not REQUIRED_INDIVIDUAL_KEYS.issubset(payload):
        raise ValueError("Incomplete stock AI context")
    _ensure_dict(payload["selected_stock"], "selected_stock")
    return payload


def validate_stock_comparison_context(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _ensure_dict(payload, "Stock comparison AI context")
    if payload.get("analysis_type") != "stock_comparison":
        raise ValueError("Invalid stock comparison AI analysis type")
    if not REQUIRED_COMPARISON_KEYS.issubset(payload):
        raise ValueError("Incomplete stock comparison AI context")
    stocks = payload["stocks"]
    if not isinstance(stocks, list) or len(stocks) < 2 or len(stocks) > 4:
        raise ValueError("Stock comparison AI context must contain 2 to 4 stocks")
    for stock in stocks:
        _ensure_dict(stock, "comparison stock")
    return payload
