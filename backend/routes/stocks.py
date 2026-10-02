from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.config.settings import Settings
from backend.services.data.fundamentals import get_stock_analysis
from backend.services.data.stock_charts import build_stock_charts, yahoo_annual_prices
from backend.services.data.yahoo import YahooFinanceClient, YahooFinanceError
from backend.services.stocks.nifty_universe import (
    NiftyUniverseError,
    load_nifty_total_market,
    nifty_sectors,
)
from backend.services.stocks.screening import list_stocks

router = APIRouter()
client: YahooFinanceClient | None = None


def _get_client() -> YahooFinanceClient:
    """Create the Yahoo client lazily so outages/rate limits cannot crash startup."""
    global client
    if client is None:
        client = YahooFinanceClient(Settings())
    return client


def _latest_statement_value(
    rows: list[dict[str, Any]],
    key: str,
) -> float | None:
    if not rows:
        return None
    return rows[0].get("values", {}).get(key)


def _enrich_public_analysis(data: dict[str, Any]) -> dict[str, Any]:
    """Add cross-statement ratios used by the analysis UI without exposing provider details."""
    f = data.get("fundamentals", {})
    balance = data.get("balance_sheet", [])

    assets = _latest_statement_value(balance, "TotalAssets")
    current_liabilities = _latest_statement_value(balance, "CurrentLiabilities")

    if (
        f.get("sector") != "Financial Services"
        and f.get("operating_profit") is not None
        and assets is not None
        and current_liabilities is not None
        and assets != current_liabilities
    ):
        f["roce"] = f["operating_profit"] / (assets - current_liabilities) * 100

    revenue = f.get("revenue")
    fcf = f.get("free_cash_flow")
    cfo = f.get("operating_cash_flow")
    profit = f.get("net_profit")
    debt = f.get("total_debt")
    cash = f.get("cash")
    ebitda = f.get("ebitda")

    if revenue not in (None, 0) and fcf is not None:
        f["fcf_margin"] = fcf / revenue * 100
    if profit not in (None, 0) and cfo is not None:
        f["cash_conversion"] = cfo / profit * 100
    if debt is not None and cash is not None:
        f["net_debt"] = debt - cash
    if (
        f.get("sector") != "Financial Services"
        and f.get("net_debt") is not None
        and ebitda not in (None, 0)
        and ebitda > 0
    ):
        f["net_debt_ebitda"] = f["net_debt"] / ebitda

    # Keep provider implementation details out of the public UI/API contract.
    f["source"] = "Fundamentals provider"
    data["warnings"] = [
        "Some ratios are derived from the latest income statement and balance sheet and may differ slightly from reported provider ratios.",
        "Historical CAGR metrics require the requested lookback period to be available and a positive starting value.",
        "Financial companies use a different valuation lens: P/B, ROE and ROA are more informative than EV/EBITDA.",
    ]
    return data


@router.get("/universe")
async def get_stock_universe(
    sector: Optional[str] = Query(default=None),
    query: Optional[str] = Query(default=None),
    min_market_cap_cr: Optional[float] = Query(default=None, ge=0),
    max_market_cap_cr: Optional[float] = Query(default=None, ge=0),
    min_pe: Optional[float] = Query(default=None, gt=0),
    max_pe: Optional[float] = Query(default=None, gt=0),
    min_roe: Optional[float] = Query(default=None),
    max_roe: Optional[float] = Query(default=None),
    min_pb: Optional[float] = Query(default=None, gt=0),
    max_pb: Optional[float] = Query(default=None, gt=0),
    min_peg: Optional[float] = Query(default=None, gt=0),
    max_peg: Optional[float] = Query(default=None, gt=0),
    min_roa: Optional[float] = Query(default=None),
    max_roa: Optional[float] = Query(default=None),
    min_debt_equity: Optional[float] = Query(default=None, ge=0),
    max_debt_equity: Optional[float] = Query(default=None, ge=0),
    min_current_ratio: Optional[float] = Query(default=None, ge=0),
    max_current_ratio: Optional[float] = Query(default=None, ge=0),
    min_ev_ebitda: Optional[float] = Query(default=None, ge=0),
    max_ev_ebitda: Optional[float] = Query(default=None, ge=0),
    min_ev_revenue: Optional[float] = Query(default=None, ge=0),
    max_ev_revenue: Optional[float] = Query(default=None, ge=0),
    min_dividend_yield: Optional[float] = Query(default=None, ge=0),
    max_dividend_yield: Optional[float] = Query(default=None, ge=0),
    include_metrics: bool = Query(default=False),
):
    try:
        has_fundamental_filter = any(
            value is not None
            for value in (
                min_market_cap_cr, max_market_cap_cr, min_pe, max_pe,
                min_roe, max_roe, min_pb, max_pb, min_peg, max_peg,
                min_roa, max_roa, min_debt_equity, max_debt_equity,
                min_current_ratio, max_current_ratio, min_ev_ebitda,
                max_ev_ebitda, min_ev_revenue, max_ev_revenue,
                min_dividend_yield, max_dividend_yield,
            )
        )

        if not include_metrics and not has_fundamental_filter:
            stocks = load_nifty_total_market()
            if sector:
                stocks = [stock for stock in stocks if stock["sector"] == sector]
            if query:
                q = query.strip().lower()
                stocks = [
                    stock for stock in stocks
                    if q in stock["symbol"].lower() or q in stock["name"].lower()
                ]
            return {
                "sector": sector,
                "sectors": nifty_sectors(),
                "stocks": stocks,
                "count": len(stocks),
                "universe": "Nifty Total Market",
                "classification_source": "NSE Indices / Nifty Total Market constituent CSV",
            }

        return list_stocks(
            _get_client(),
            sector=sector, query=query,
            min_market_cap_cr=min_market_cap_cr, max_market_cap_cr=max_market_cap_cr,
            min_pe=min_pe, max_pe=max_pe, min_roe=min_roe, max_roe=max_roe,
            min_pb=min_pb, max_pb=max_pb, min_peg=min_peg, max_peg=max_peg,
            min_roa=min_roa, max_roa=max_roa,
            min_debt_equity=min_debt_equity, max_debt_equity=max_debt_equity,
            min_current_ratio=min_current_ratio, max_current_ratio=max_current_ratio,
            min_ev_ebitda=min_ev_ebitda, max_ev_ebitda=max_ev_ebitda,
            min_ev_revenue=min_ev_revenue, max_ev_revenue=max_ev_revenue,
            min_dividend_yield=min_dividend_yield, max_dividend_yield=max_dividend_yield,
        )
    except (NiftyUniverseError, YahooFinanceError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/charts")
async def get_stock_charts(symbol: str):
    try:
        normalized = symbol.strip().upper()
        history = _get_client().financial_history(normalized)
        prices = yahoo_annual_prices(normalized, years=7)
        return {
            "symbol": normalized,
            "charts": build_stock_charts(history, prices),
            "price_source": "Market price history",
            "notes": [
                "EPS and revenue charts show annual year-over-year growth.",
                "ROE trend is derived from annual net profit and average shareholder equity.",
                "Price CAGR uses annual closing prices and is shown as rolling 3-year and 5-year CAGR.",
            ],
        }
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}")
async def get_stock(symbol: str):
    try:
        return _enrich_public_analysis(get_stock_analysis(_get_client(), symbol))
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{symbol}/fundamentals")
async def get_fundamentals(symbol: str):
    try:
        return _enrich_public_analysis(get_stock_analysis(_get_client(), symbol))["fundamentals"]
    except YahooFinanceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
