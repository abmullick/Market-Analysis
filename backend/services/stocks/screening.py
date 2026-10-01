from __future__ import annotations

from typing import Any

from backend.services.data.yahoo import YahooFinanceClient, number
from backend.services.stocks.nifty_universe import (
    load_nifty_total_market,
    nifty_sectors,
)


def _matches(
    value: float | None,
    minimum: float | None,
    maximum: float | None,
) -> bool:
    if minimum is not None and (value is None or value < minimum):
        return False
    if maximum is not None and (value is None or value > maximum):
        return False
    return True


def list_stocks(
    client: YahooFinanceClient,
    sector: str | None = None,
    query: str | None = None,
    min_market_cap_cr: float | None = None,
    max_market_cap_cr: float | None = None,
    min_pe: float | None = None,
    max_pe: float | None = None,
    min_pb: float | None = None,
    max_pb: float | None = None,
    min_peg: float | None = None,
    max_peg: float | None = None,
    min_roa: float | None = None,
    max_roa: float | None = None,
    min_roe: float | None = None,
    max_roe: float | None = None,
    min_debt_equity: float | None = None,
    max_debt_equity: float | None = None,
    min_current_ratio: float | None = None,
    max_current_ratio: float | None = None,
    min_ev_ebitda: float | None = None,
    max_ev_ebitda: float | None = None,
    min_ev_revenue: float | None = None,
    max_ev_revenue: float | None = None,
    min_dividend_yield: float | None = None,
    max_dividend_yield: float | None = None,
) -> dict[str, Any]:

    items = load_nifty_total_market()

    if sector:
        items = [item for item in items if item["sector"] == sector]

    if query:
        q = query.strip().lower()
        items = [
            item
            for item in items
            if q in item["symbol"].lower() or q in item["name"].lower()
        ]

    stocks: list[dict[str, Any]] = []

    for item in items:
        try:
            quote = client.quote_summary(item["symbol"])

            market_cap = number(quote.get("marketCap"))
            pe = number(quote.get("trailingPE"))
            pb = number(quote.get("priceToBook"))
            peg = number(quote.get("pegRatio"))
            roe = number(quote.get("returnOnEquity"))
            roa = number(quote.get("returnOnAssets"))
            debt_equity = number(quote.get("debtToEquity"))
            current_ratio = number(quote.get("currentRatio"))
            ev_ebitda = number(quote.get("enterpriseToEbitda"))
            ev_revenue = number(quote.get("enterpriseToRevenue"))
            dividend_yield = number(quote.get("dividendYield"))

            stocks.append({
                **item,
                "market_cap": market_cap,
                "market_cap_cr": (
                    market_cap / 1e7
                    if market_cap is not None
                    else None
                ),
                "pe": pe,
                "pb": pb,
                "peg": peg,
                "roe": roe * 100 if roe is not None else None,
                "roa": roa * 100 if roa is not None else None,
                "debt_equity": debt_equity,
                "current_ratio": current_ratio,
                "ev_ebitda": ev_ebitda,
                "ev_revenue": ev_revenue,
                "dividend_yield": (
                    dividend_yield * 100
                    if dividend_yield is not None
                    else None
                ),
                "price": number(quote.get("regularMarketPrice")),
            })

        except Exception:
            stocks.append({
                **item,
                "market_cap": None,
                "market_cap_cr": None,
                "pe": None,
                "pb": None,
                "peg": None,
                "roe": None,
                "roa": None,
                "debt_equity": None,
                "current_ratio": None,
                "ev_ebitda": None,
                "ev_revenue": None,
                "dividend_yield": None,
                "price": None,
            })

    stocks = [
        s for s in stocks
        if _matches(s["market_cap_cr"], min_market_cap_cr, max_market_cap_cr)
        and _matches(s["pe"], min_pe, max_pe)
        and _matches(s["pb"], min_pb, max_pb)
        and _matches(s["peg"], min_peg, max_peg)
        and _matches(s["roa"], min_roa, max_roa)
        and _matches(s["roe"], min_roe, max_roe)
        and _matches(
            s["debt_equity"],
            min_debt_equity,
            max_debt_equity,
        )
        and _matches(
            s["current_ratio"],
            min_current_ratio,
            max_current_ratio,
        )
        and _matches(
            s["ev_ebitda"],
            min_ev_ebitda,
            max_ev_ebitda,
        )
        and _matches(
            s["ev_revenue"],
            min_ev_revenue,
            max_ev_revenue,
        )
        and _matches(
            s["dividend_yield"],
            min_dividend_yield,
            max_dividend_yield,
        )
    ]

    stocks.sort(
        key=lambda s: (
            s["market_cap_cr"] is not None,
            s["market_cap_cr"] or 0,
        ),
        reverse=True,
    )

    return {
        "sector": sector,
        "stocks": stocks,
        "count": len(stocks),
        "universe": "Nifty Total Market",
        "classification_source": (
            "NSE Indices / Nifty Total Market constituent CSV"
        ),
        "sectors": nifty_sectors(),
    }
