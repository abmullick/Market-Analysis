from __future__ import annotations

from typing import Any

from backend.services.data.yahoo import YahooFinanceClient, number
from backend.services.stocks.nifty_universe import load_nifty_total_market, nifty_sectors

LIQUIDITY_THRESHOLDS_CR = {"high": 50.0, "moderate": 10.0, "low": 2.0}


def _liquidity_status(avg_traded_value_cr: float | None) -> str | None:
    if avg_traded_value_cr is None:
        return None
    if avg_traded_value_cr >= 50:
        return "high"
    if avg_traded_value_cr >= 10:
        return "moderate"
    if avg_traded_value_cr >= 2:
        return "low"
    return "illiquid"


def _matches(value: float | None, minimum: float | None, maximum: float | None) -> bool:
    if minimum is not None and (value is None or value < minimum):
        return False
    if maximum is not None and (value is None or value > maximum):
        return False
    return True


def _peg_from_history(client: YahooFinanceClient, symbol: str, pe: float | None) -> float | None:
    if pe is None or pe <= 0:
        return None
    try:
        history = client.financial_history(symbol)
        rows = history.get("income", {}).get("annualDilutedEPS", [])
        series: list[tuple[str, float]] = []
        for row in rows:
            date = str(row.get("asOfDate") or row.get("periodEnd") or "")[:10]
            value = row.get("reportedValue")
            if isinstance(value, dict):
                value = value.get("raw")
            value = number(value)
            if date and value is not None:
                series.append((date, value))
        series = sorted({date: value for date, value in series}.items())
        if len(series) < 4:
            return None
        end_date, end_eps = series[-1]
        target_year = int(end_date[:4]) - 3
        candidates = [(date, value) for date, value in series[:-1] if int(date[:4]) <= target_year]
        if not candidates:
            return None
        start_date, start_eps = candidates[-1]
        actual_years = int(end_date[:4]) - int(start_date[:4])
        if actual_years < 3 or start_eps <= 0 or end_eps <= 0:
            return None
        eps_cagr = (end_eps / start_eps) ** (1 / actual_years) - 1
        return pe / (eps_cagr * 100) if eps_cagr > 0 else None
    except Exception:
        return None


def _cached_screener_volume(client: YahooFinanceClient, symbol: str) -> float | None:
    """Read the already-cached Screener page for current trading volume.

    This is deliberately a fallback only. It avoids another network request because
    quote_summary() has just populated the same Screener page cache for this symbol.
    """
    try:
        _, extracted = client._screener._extract(symbol)
        ratios = extracted.get("ratios", {})
        for key in ("Volume", "Volume (shares)", "Volume (Qty)"):
            value = number(ratios.get(key))
            if value is not None:
                return value
    except Exception:
        pass
    return None


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
    include_liquidity: bool = False,
) -> dict[str, Any]:
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
            price = number(quote.get("regularMarketPrice"))

            # Prefer Yahoo's rolling 3-month average volume when it is present.
            # For NSE fundamentals Screener is the primary source and normally
            # does not expose that Yahoo field, so fall back to the current
            # Screener volume from the page already cached by quote_summary().
            avg_volume_3m = number(quote.get("averageDailyVolume3Month"))
            liquidity_source = None
            observations = None
            if include_liquidity:
                if avg_volume_3m is not None:
                    liquidity_source = "Yahoo Finance 3-month average daily volume × current price"
                else:
                    avg_volume_3m = _cached_screener_volume(client, item["symbol"])
                    if avg_volume_3m is not None:
                        liquidity_source = "Screener current trading volume × current price (fallback proxy)"

            avg_traded_value_cr = None
            if include_liquidity and avg_volume_3m is not None and price is not None:
                avg_traded_value_cr = avg_volume_3m * price / 1e7
                observations = 1 if liquidity_source and "fallback" in liquidity_source else None

            pe = number(quote.get("trailingPE"))
            peg = number(quote.get("pegRatio")) or _peg_from_history(client, item["symbol"], pe)
            stocks.append({
                **item,
                "market_cap": market_cap,
                "market_cap_cr": market_cap / 1e7 if market_cap is not None else None,
                "pe": pe,
                "pb": number(quote.get("priceToBook")),
                "peg": peg,
                "roe": number(quote.get("returnOnEquity")) * 100 if number(quote.get("returnOnEquity")) is not None else None,
                "roa": number(quote.get("returnOnAssets")) * 100 if number(quote.get("returnOnAssets")) is not None else None,
                "debt_equity": number(quote.get("debtToEquity")),
                "current_ratio": number(quote.get("currentRatio")),
                "ev_ebitda": number(quote.get("enterpriseToEbitda")),
                "ev_revenue": number(quote.get("enterpriseToRevenue")),
                "dividend_yield": number(quote.get("dividendYield")) * 100 if number(quote.get("dividendYield")) is not None else None,
                "price": price,
                "avg_daily_volume_3m": avg_volume_3m if include_liquidity else None,
                "avg_daily_traded_value_3m_cr": avg_traded_value_cr,
                "trading_observations_3m": observations,
                "liquidity_status": _liquidity_status(avg_traded_value_cr),
                "liquidity_source": liquidity_source,
            })
        except Exception:
            stocks.append({
                **item,
                "market_cap": None, "market_cap_cr": None, "pe": None, "pb": None,
                "peg": None, "roe": None, "roa": None, "debt_equity": None,
                "current_ratio": None, "ev_ebitda": None, "ev_revenue": None,
                "dividend_yield": None, "price": None, "avg_daily_volume_3m": None,
                "avg_daily_traded_value_3m_cr": None, "trading_observations_3m": None,
                "liquidity_status": None, "liquidity_source": None,
            })

    stocks = [
        s for s in stocks
        if _matches(s["market_cap_cr"], min_market_cap_cr, max_market_cap_cr)
        and _matches(s["pe"], min_pe, max_pe)
        and _matches(s["pb"], min_pb, max_pb)
        and _matches(s["peg"], min_peg, max_peg)
        and _matches(s["roa"], min_roa, max_roa)
        and _matches(s["roe"], min_roe, max_roe)
        and _matches(s["debt_equity"], min_debt_equity, max_debt_equity)
        and _matches(s["current_ratio"], min_current_ratio, max_current_ratio)
        and _matches(s["ev_ebitda"], min_ev_ebitda, max_ev_ebitda)
        and _matches(s["ev_revenue"], min_ev_revenue, max_ev_revenue)
        and _matches(s["dividend_yield"], min_dividend_yield, max_dividend_yield)
    ]
    stocks.sort(key=lambda s: (s["market_cap_cr"] is not None, s["market_cap_cr"] or 0), reverse=True)
    return {
        "sector": sector,
        "stocks": stocks,
        "count": len(stocks),
        "universe": "Nifty Total Market",
        "classification_source": "NSE Indices / Nifty Total Market constituent CSV",
        "liquidity_method": "Yahoo Finance 3-month average daily volume × current price; Screener current-volume fallback when Yahoo average volume is unavailable",
        "liquidity_thresholds_cr": {"high": 50, "moderate": 10, "low": 2, "illiquid": 0},
        "liquidity_loaded": include_liquidity,
        "sectors": nifty_sectors(),
    }
