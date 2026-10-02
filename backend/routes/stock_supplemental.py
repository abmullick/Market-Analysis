from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.routes import stocks as stock_routes
from backend.services.data.fundamentals import get_stock_analysis
from backend.services.data.yahoo import YahooFinanceError, number

router = APIRouter()


def _yahoo_supplemental(symbol: str) -> dict[str, float | None]:
    """Fetch only market-data fields that are intentionally supplemental to Screener."""
    client = stock_routes._get_client()
    try:
        payload = client._get_json(
            f"/v10/finance/quoteSummary/{symbol}",
            {"modules": "defaultKeyStatistics,summaryDetail"},
        )
    except Exception:
        return {"forward_pe": None, "beta": None}

    result = (payload.get("quoteSummary", {}).get("result") or [{}])[0]
    out: dict[str, float | None] = {"forward_pe": None, "beta": None}
    for module_name in ("defaultKeyStatistics", "summaryDetail"):
        module = result.get(module_name) or {}
        if out["forward_pe"] is None:
            out["forward_pe"] = number(module.get("forwardPE"))
        if out["beta"] is None:
            out["beta"] = number(module.get("beta"))
    return out


def _latest(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    value = (rows[0].get("values") or {}).get(key)
    return number(value)


def _supplement(data: dict[str, Any], symbol: str) -> dict[str, Any]:
    f = data.get("fundamentals", {})
    income = data.get("income_statement", [])
    balance = data.get("balance_sheet", [])
    financial = str(f.get("sector") or "").lower() == "financial services"

    revenue = number(f.get("revenue")) or _latest(income, "TotalRevenue")
    gross_profit = number(f.get("gross_profit")) or _latest(income, "GrossProfit")
    total_debt = number(f.get("total_debt")) or _latest(balance, "TotalDebt")
    equity = _latest(balance, "StockholdersEquity")
    cash = number(f.get("cash"))
    if cash is None:
        cash = _latest(balance, "CashCashEquivalentsAndShortTermInvestments")
    current_assets = _latest(balance, "CurrentAssets")
    current_liabilities = _latest(balance, "CurrentLiabilities")
    inventory = _latest(balance, "Inventory")

    computed: dict[str, Any] = {
        "enterprise_value": f.get("enterprise_value"),
        "ebitda": f.get("ebitda"),
        "ev_ebitda": f.get("ev_ebitda"),
        "ev_revenue": f.get("ev_revenue"),
        "gross_margin": f.get("gross_margin"),
        "current_ratio": f.get("current_ratio"),
        "quick_ratio": f.get("quick_ratio"),
        "debt_equity": f.get("debt_equity"),
    }

    # Compute conventional non-financial-company metrics when the source did not provide them.
    if not financial:
        market_cap = number(f.get("market_cap"))
        if computed["enterprise_value"] is None and market_cap is not None and total_debt is not None and cash is not None:
            computed["enterprise_value"] = market_cap + total_debt - cash
        if computed["ev_ebitda"] is None and computed["enterprise_value"] is not None and computed["ebitda"] not in (None, 0):
            computed["ev_ebitda"] = computed["enterprise_value"] / computed["ebitda"]
        if computed["ev_revenue"] is None and computed["enterprise_value"] is not None and revenue not in (None, 0):
            computed["ev_revenue"] = computed["enterprise_value"] / revenue
        if computed["gross_margin"] is None and gross_profit is not None and revenue not in (None, 0):
            computed["gross_margin"] = gross_profit / revenue * 100
        if computed["current_ratio"] is None and current_assets is not None and current_liabilities not in (None, 0):
            computed["current_ratio"] = current_assets / current_liabilities
        if computed["quick_ratio"] is None and current_assets is not None and current_liabilities not in (None, 0):
            computed["quick_ratio"] = (current_assets - (inventory or 0)) / current_liabilities

    # Debt / Equity is meaningful for lenders as well and is therefore computed for all sectors.
    if computed["debt_equity"] is None and total_debt is not None and equity not in (None, 0):
        computed["debt_equity"] = total_debt / equity

    yahoo = _yahoo_supplemental(symbol)

    # These metrics are intentionally marked N/M for financial companies.
    nm = {
        "enterprise_value": financial,
        "ebitda": financial,
        "ev_ebitda": financial,
        "ev_revenue": financial,
        "gross_margin": financial,
        "current_ratio": financial,
        "quick_ratio": financial,
    }

    return {
        "symbol": symbol,
        "financial_company": financial,
        "computed": computed,
        "yahoo": yahoo,
        "not_meaningful": nm,
        "source_note": "Screener.in remains the primary Indian fundamental-data source. Forward P/E and Beta are supplemental Yahoo Finance market data.",
    }


@router.get("/{symbol}/supplemental")
async def get_stock_supplemental(symbol: str):
    normalized = symbol.strip().upper()
    try:
        data = stock_routes._enrich_public_analysis(get_stock_analysis(stock_routes._get_client(), normalized))
        return _supplement(data, normalized)
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
