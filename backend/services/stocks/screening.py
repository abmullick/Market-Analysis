from __future__ import annotations

from typing import Any

from backend.services.data.yahoo import YahooFinanceClient, number
from backend.services.stocks.nifty_universe import load_nifty_total_market, nifty_sectors


def _matches(value: float | None, minimum: float | None, maximum: float | None) -> bool:
    if minimum is not None and (value is None or value < minimum):
        return False
    if maximum is not None and (value is None or value > maximum):
        return False
    return True


def list_stocks(client: YahooFinanceClient, sector: str | None = None, query: str | None = None,
                min_market_cap_cr: float | None = None, max_market_cap_cr: float | None = None,
                min_pe: float | None = None, max_pe: float | None = None,
                min_roe: float | None = None, max_roe: float | None = None) -> dict[str, Any]:
    items = load_nifty_total_market()
    if sector:
        items = [item for item in items if item["sector"] == sector]
    if query:
        q = query.strip().lower()
        items = [item for item in items if q in item["symbol"].lower() or q in item["name"].lower()]

    stocks: list[dict[str, Any]] = []
    for item in items:
        try:
            quote = client.quote_summary(item["symbol"])
            market_cap = number(quote.get("marketCap"))
            pe = number(quote.get("trailingPE"))
            roe = number(quote.get("returnOnEquity"))
            stocks.append({**item, "market_cap": market_cap, "market_cap_cr": market_cap / 1e7 if market_cap is not None else None,
                           "pe": pe, "roe": roe * 100 if roe is not None else None,
                           "price": number(quote.get("regularMarketPrice"))})
        except Exception:
            stocks.append({**item, "market_cap": None, "market_cap_cr": None, "pe": None, "roe": None, "price": None})

    stocks = [s for s in stocks if _matches(s["market_cap_cr"], min_market_cap_cr, max_market_cap_cr)
              and _matches(s["pe"], min_pe, max_pe) and _matches(s["roe"], min_roe, max_roe)]
    stocks.sort(key=lambda s: (s["market_cap_cr"] is not None, s["market_cap_cr"] or 0), reverse=True)
    return {"sector": sector, "stocks": stocks, "count": len(stocks), "universe": "Nifty Total Market",
            "classification_source": "NSE Indices / Nifty Total Market constituent CSV", "sectors": nifty_sectors()}
