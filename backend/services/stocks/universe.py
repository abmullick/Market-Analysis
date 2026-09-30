from __future__ import annotations

from typing import Any

from backend.services.data.yahoo import YahooFinanceClient, number

# Large, liquid NSE universe used by the stock-selection screen. The list is
# intentionally kept local so the selector does not depend on a third-party
# screener page at runtime. Metrics are fetched live from Yahoo when a sector
# is selected.
STOCK_UNIVERSE: list[dict[str, str]] = [
    {"symbol": "ACC.NS", "name": "ACC Ltd.", "sector": "Construction Materials"},
    {"symbol": "ADANIENT.NS", "name": "Adani Enterprises Ltd.", "sector": "Metals & Mining"},
    {"symbol": "ADANIGREEN.NS", "name": "Adani Green Energy Ltd.", "sector": "Power"},
    {"symbol": "ADANIPORTS.NS", "name": "Adani Ports and Special Economic Zone Ltd.", "sector": "Services"},
    {"symbol": "AMBUJACEM.NS", "name": "Ambuja Cements Ltd.", "sector": "Construction Materials"},
    {"symbol": "APOLLOHOSP.NS", "name": "Apollo Hospitals Enterprise Ltd.", "sector": "Healthcare"},
    {"symbol": "ASIANPAINT.NS", "name": "Asian Paints Ltd.", "sector": "Consumer Durables"},
    {"symbol": "DMART.NS", "name": "Avenue Supermarts Ltd.", "sector": "Consumer Services"},
    {"symbol": "AXISBANK.NS", "name": "Axis Bank Ltd.", "sector": "Financial Services"},
    {"symbol": "BAJAJ-AUTO.NS", "name": "Bajaj Auto Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "BAJFINANCE.NS", "name": "Bajaj Finance Ltd.", "sector": "Financial Services"},
    {"symbol": "BAJAJFINSV.NS", "name": "Bajaj Finserv Ltd.", "sector": "Financial Services"},
    {"symbol": "BAJAJHLDNG.NS", "name": "Bajaj Holdings & Investment Ltd.", "sector": "Financial Services"},
    {"symbol": "BANDHANBNK.NS", "name": "Bandhan Bank Ltd.", "sector": "Financial Services"},
    {"symbol": "BANKBARODA.NS", "name": "Bank of Baroda", "sector": "Financial Services"},
    {"symbol": "BERGEPAINT.NS", "name": "Berger Paints India Ltd.", "sector": "Consumer Durables"},
    {"symbol": "BPCL.NS", "name": "Bharat Petroleum Corporation Ltd.", "sector": "Oil, Gas & Consumable Fuels"},
    {"symbol": "BHARTIARTL.NS", "name": "Bharti Airtel Ltd.", "sector": "Telecommunication"},
    {"symbol": "BIOCON.NS", "name": "Biocon Ltd.", "sector": "Healthcare"},
    {"symbol": "BOSCHLTD.NS", "name": "Bosch Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "BRITANNIA.NS", "name": "Britannia Industries Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "CHOLAFIN.NS", "name": "Cholamandalam Investment and Finance Company Ltd.", "sector": "Financial Services"},
    {"symbol": "CIPLA.NS", "name": "Cipla Ltd.", "sector": "Healthcare"},
    {"symbol": "COALINDIA.NS", "name": "Coal India Ltd.", "sector": "Oil, Gas & Consumable Fuels"},
    {"symbol": "COLPAL.NS", "name": "Colgate-Palmolive (India) Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "DABUR.NS", "name": "Dabur India Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "DIVISLAB.NS", "name": "Divi's Laboratories Ltd.", "sector": "Healthcare"},
    {"symbol": "DLF.NS", "name": "DLF Ltd.", "sector": "Realty"},
    {"symbol": "DRREDDY.NS", "name": "Dr. Reddy's Laboratories Ltd.", "sector": "Healthcare"},
    {"symbol": "EICHERMOT.NS", "name": "Eicher Motors Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "NYKAA.NS", "name": "FSN E-Commerce Ventures Ltd.", "sector": "Consumer Services"},
    {"symbol": "GAIL.NS", "name": "GAIL (India) Ltd.", "sector": "Oil, Gas & Consumable Fuels"},
    {"symbol": "GLAND.NS", "name": "Gland Pharma Ltd.", "sector": "Healthcare"},
    {"symbol": "GODREJCP.NS", "name": "Godrej Consumer Products Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "GRASIM.NS", "name": "Grasim Industries Ltd.", "sector": "Construction Materials"},
    {"symbol": "HAVELLS.NS", "name": "Havells India Ltd.", "sector": "Consumer Durables"},
    {"symbol": "HCLTECH.NS", "name": "HCL Technologies Ltd.", "sector": "Information Technology"},
    {"symbol": "HDFCAMC.NS", "name": "HDFC Asset Management Company Ltd.", "sector": "Financial Services"},
    {"symbol": "HDFCBANK.NS", "name": "HDFC Bank Ltd.", "sector": "Financial Services"},
    {"symbol": "HDFCLIFE.NS", "name": "HDFC Life Insurance Company Ltd.", "sector": "Financial Services"},
    {"symbol": "HEROMOTOCO.NS", "name": "Hero MotoCorp Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "HINDALCO.NS", "name": "Hindalco Industries Ltd.", "sector": "Metals & Mining"},
    {"symbol": "HINDUNILVR.NS", "name": "Hindustan Unilever Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "ICICIBANK.NS", "name": "ICICI Bank Ltd.", "sector": "Financial Services"},
    {"symbol": "ICICIGI.NS", "name": "ICICI Lombard General Insurance Company Ltd.", "sector": "Financial Services"},
    {"symbol": "ICICIPRULI.NS", "name": "ICICI Prudential Life Insurance Company Ltd.", "sector": "Financial Services"},
    {"symbol": "IOC.NS", "name": "Indian Oil Corporation Ltd.", "sector": "Oil, Gas & Consumable Fuels"},
    {"symbol": "INDUSTOWER.NS", "name": "Indus Towers Ltd.", "sector": "Telecommunication"},
    {"symbol": "INDUSINDBK.NS", "name": "IndusInd Bank Ltd.", "sector": "Financial Services"},
    {"symbol": "NAUKRI.NS", "name": "Info Edge (India) Ltd.", "sector": "Consumer Services"},
    {"symbol": "INFY.NS", "name": "Infosys Ltd.", "sector": "Information Technology"},
    {"symbol": "INDIGO.NS", "name": "InterGlobe Aviation Ltd.", "sector": "Services"},
    {"symbol": "ITC.NS", "name": "ITC Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "JSWSTEEL.NS", "name": "JSW Steel Ltd.", "sector": "Metals & Mining"},
    {"symbol": "JUBLFOOD.NS", "name": "Jubilant FoodWorks Ltd.", "sector": "Consumer Services"},
    {"symbol": "KOTAKBANK.NS", "name": "Kotak Mahindra Bank Ltd.", "sector": "Financial Services"},
    {"symbol": "LT.NS", "name": "Larsen & Toubro Ltd.", "sector": "Construction"},
    {"symbol": "LUPIN.NS", "name": "Lupin Ltd.", "sector": "Healthcare"},
    {"symbol": "M&M.NS", "name": "Mahindra & Mahindra Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "MARICO.NS", "name": "Marico Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "MARUTI.NS", "name": "Maruti Suzuki India Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "MUTHOOTFIN.NS", "name": "Muthoot Finance Ltd.", "sector": "Financial Services"},
    {"symbol": "NESTLEIND.NS", "name": "Nestle India Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "NMDC.NS", "name": "NMDC Ltd.", "sector": "Metals & Mining"},
    {"symbol": "NTPC.NS", "name": "NTPC Ltd.", "sector": "Power"},
    {"symbol": "ONGC.NS", "name": "Oil & Natural Gas Corporation Ltd.", "sector": "Oil, Gas & Consumable Fuels"},
    {"symbol": "PAYTM.NS", "name": "One 97 Communications Ltd.", "sector": "Financial Services"},
    {"symbol": "PIIND.NS", "name": "PI Industries Ltd.", "sector": "Chemicals"},
    {"symbol": "PIDILITIND.NS", "name": "Pidilite Industries Ltd.", "sector": "Chemicals"},
    {"symbol": "PEL.NS", "name": "Piramal Enterprises Ltd.", "sector": "Financial Services"},
    {"symbol": "POWERGRID.NS", "name": "Power Grid Corporation of India Ltd.", "sector": "Power"},
    {"symbol": "PGHH.NS", "name": "Procter & Gamble Hygiene & Health Care Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "PNB.NS", "name": "Punjab National Bank", "sector": "Financial Services"},
    {"symbol": "RELIANCE.NS", "name": "Reliance Industries Ltd.", "sector": "Oil, Gas & Consumable Fuels"},
    {"symbol": "SBICARD.NS", "name": "SBI Cards and Payment Services Ltd.", "sector": "Financial Services"},
    {"symbol": "SBILIFE.NS", "name": "SBI Life Insurance Company Ltd.", "sector": "Financial Services"},
    {"symbol": "SHREECEM.NS", "name": "Shree Cement Ltd.", "sector": "Construction Materials"},
    {"symbol": "SIEMENS.NS", "name": "Siemens Ltd.", "sector": "Capital Goods"},
    {"symbol": "SRF.NS", "name": "SRF Ltd.", "sector": "Chemicals"},
    {"symbol": "SBIN.NS", "name": "State Bank of India", "sector": "Financial Services"},
    {"symbol": "SAIL.NS", "name": "Steel Authority of India Ltd.", "sector": "Metals & Mining"},
    {"symbol": "SUNPHARMA.NS", "name": "Sun Pharmaceutical Industries Ltd.", "sector": "Healthcare"},
    {"symbol": "TCS.NS", "name": "Tata Consultancy Services Ltd.", "sector": "Information Technology"},
    {"symbol": "TATACONSUM.NS", "name": "Tata Consumer Products Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "TATAMOTORS.NS", "name": "Tata Motors Ltd.", "sector": "Automobile and Auto Components"},
    {"symbol": "TATASTEEL.NS", "name": "Tata Steel Ltd.", "sector": "Metals & Mining"},
    {"symbol": "TECHM.NS", "name": "Tech Mahindra Ltd.", "sector": "Information Technology"},
    {"symbol": "TITAN.NS", "name": "Titan Company Ltd.", "sector": "Consumer Durables"},
    {"symbol": "TORNTPHARM.NS", "name": "Torrent Pharmaceuticals Ltd.", "sector": "Healthcare"},
    {"symbol": "ULTRACEMCO.NS", "name": "UltraTech Cement Ltd.", "sector": "Construction Materials"},
    {"symbol": "MCDOWELL-N.NS", "name": "United Spirits Ltd.", "sector": "Fast Moving Consumer Goods"},
    {"symbol": "UPL.NS", "name": "UPL Ltd.", "sector": "Chemicals"},
    {"symbol": "VEDL.NS", "name": "Vedanta Ltd.", "sector": "Metals & Mining"},
    {"symbol": "WIPRO.NS", "name": "Wipro Ltd.", "sector": "Information Technology"},
    {"symbol": "ZOMATO.NS", "name": "Zomato Ltd.", "sector": "Consumer Services"},
    {"symbol": "ZYDUSLIFE.NS", "name": "Zydus Lifesciences Ltd.", "sector": "Healthcare"},
]


def sectors() -> list[str]:
    return sorted({item["sector"] for item in STOCK_UNIVERSE})


def _matches(value: float | None, minimum: float | None, maximum: float | None) -> bool:
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
    max_pe: float | None = None,
    min_roe: float | None = None,
) -> dict[str, Any]:
    items = STOCK_UNIVERSE
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
            stocks.append({
                **item,
                "market_cap": market_cap,
                "market_cap_cr": market_cap / 1e7 if market_cap is not None else None,
                "pe": pe,
                "roe": roe * 100 if roe is not None else None,
                "price": number(quote.get("regularMarketPrice")),
            })
        except Exception:
            # Keep the stock selectable even if Yahoo temporarily omits a metric.
            stocks.append({**item, "market_cap": None, "market_cap_cr": None, "pe": None, "roe": None, "price": None})

    stocks = [
        stock for stock in stocks
        if _matches(stock["market_cap_cr"], min_market_cap_cr, max_market_cap_cr)
        and _matches(stock["pe"], None, max_pe)
        and _matches(stock["roe"], min_roe, None)
    ]
    stocks.sort(key=lambda x: x["name"].lower())
    return {"sectors": sectors(), "stocks": stocks, "count": len(stocks)}
