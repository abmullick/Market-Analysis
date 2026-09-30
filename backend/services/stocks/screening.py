from __future__ import annotations

from typing import Any

from backend.services.data.yahoo import YahooFinanceClient, number
from backend.services.stocks.universe import STOCK_UNIVERSE, _matches

# Additional liquid/representative chemical-sector names. The base universe is
# retained for backward compatibility; these additions make the Chemicals
# selector materially broader instead of showing only four names.
CHEMICAL_STOCKS: list[dict[str, str]] = [
    {"symbol": "AARTIIND.NS", "name": "Aarti Industries Ltd.", "sector": "Chemicals"},
    {"symbol": "ATUL.NS", "name": "Atul Ltd.", "sector": "Chemicals"},
    {"symbol": "COROMANDEL.NS", "name": "Coromandel International Ltd.", "sector": "Chemicals"},
    {"symbol": "DEEPAKNTR.NS", "name": "Deepak Nitrite Ltd.", "sector": "Chemicals"},
    {"symbol": "FINEORG.NS", "name": "Fine Organic Industries Ltd.", "sector": "Chemicals"},
    {"symbol": "FLUOROCHEM.NS", "name": "Gujarat Fluorochemicals Ltd.", "sector": "Chemicals"},
    {"symbol": "GALAXYSURF.NS", "name": "Galaxy Surfactants Ltd.", "sector": "Chemicals"},
    {"symbol": "HSCL.NS", "name": "Himadri Speciality Chemical Ltd.", "sector": "Chemicals"},
    {"symbol": "LINDEINDIA.NS", "name": "Linde India Ltd.", "sector": "Chemicals"},
    {"symbol": "NAVINFLUOR.NS", "name": "Navin Fluorine International Ltd.", "sector": "Chemicals"},
    {"symbol": "TATACHEM.NS", "name": "Tata Chemicals Ltd.", "sector": "Chemicals"},
    {"symbol": "VINATIORGA.NS", "name": "Vinati Organics Ltd.", "sector": "Chemicals"},
    {"symbol": "SUMICHEM.NS", "name": "Sumitomo Chemical India Ltd.", "sector": "Chemicals"},
    {"symbol": "CLEAN.NS", "name": "Clean Science and Technology Ltd.", "sector": "Chemicals"},
]

STOCKS = list({item["symbol"]: item for item in [*STOCK_UNIVERSE, *CHEMICAL_STOCKS]}.values())


def sectors() -> list[str]:
    return sorted({item["sector"] for item in STOCKS})


def list_stocks(
    client: YahooFinanceClient,
    sector: str | None = None,
    query: str | None = None,
    min_market_cap_cr: float | None = None,
    max_market_cap_cr: float | None = None,
    min_pe: float | None = None,
    max_pe: float | None = None,
    min_roe: float | None = None,
    max_roe: float | None = None,
) -> dict[str, Any]:
    items = STOCKS
    if sector:
        items = [item for item in items if item["sector"] == sector]
    if query:
        q = query.strip().lower()
        items = [
            item for item in items
            if q in item["symbol"].lower() or q in item["name"].lower()
        ]

    stocks: list[dict[str, Any]] = []
    for item in items:
        try:
            quote = client.quote_summary(item["symbol"])
            market_cap = number(quote.get("marketCap"))
            pe = number(quote.get("trailingPE"))
            roe = number(quote.get("returnOnEquity"))
            stocks.append({
                **item,
                "market_cap": market_cap,
                "market_cap_cr": market_cap / 1e7 if market_cap is not None else None,
                "pe": pe,
                "roe": roe * 100 if roe is not None else None,
                "price": number(quote.get("regularMarketPrice")),
            })
        except Exception:
            stocks.append({
                **item,
                "market_cap": None,
                "market_cap_cr": None,
                "pe": None,
                "roe": None,
                "price": None,
            })

    stocks = [
        stock for stock in stocks
        if _matches(stock["market_cap_cr"], min_market_cap_cr, max_market_cap_cr)
        and _matches(stock["pe"], min_pe, max_pe)
        and _matches(stock["roe"], min_roe, max_roe)
    ]

    stocks.sort(
        key=lambda stock: (
            stock["market_cap_cr"] is not None,
            stock["market_cap_cr"] or 0,
        ),
        reverse=True,
    )

    return {
        "sector": sector,
        "stocks": stocks,
        "count": len(stocks),
    }
