from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from backend.services.data.yahoo import YahooFinanceClient, number
from backend.services.stocks.nifty_universe import load_nifty_total_market, nifty_sectors

# Stock screening is I/O-bound: each constituent requires an external
# fundamentals request, and some stocks require a second historical-EPS
# request for PEG. Keep this bounded rather than creating an unbounded number
# of outbound requests. Sixteen workers matches the proven concurrency level
# used elsewhere in the application.
SCREENING_MAX_WORKERS = 16


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


def _fetch_stock(client: YahooFinanceClient, item: dict[str, Any]) -> dict[str, Any]:
    """Fetch one stock's quote and any required PEG history."""
    try:
        quote = client.quote_summary(item["symbol"])
        market_cap = number(quote.get("marketCap"))
        price = number(quote.get("regularMarketPrice"))
        pe = number(quote.get("trailingPE"))
        peg = number(quote.get("pegRatio")) or _peg_from_history(client, item["symbol"], pe)
        roe = number(quote.get("returnOnEquity"))
        roa = number(quote.get("returnOnAssets"))
        dividend_yield = number(quote.get("dividendYield"))
        return {
            **item,
            "market_cap": market_cap,
            "market_cap_cr": market_cap / 1e7 if market_cap is not None else None,
            "pe": pe,
            "pb": number(quote.get("priceToBook")),
            "peg": peg,
            "roe": roe * 100 if roe is not None else None,
            "roa": roa * 100 if roa is not None else None,
            "debt_equity": number(quote.get("debtToEquity")),
            "current_ratio": number(quote.get("currentRatio")),
            "ev_ebitda": number(quote.get("enterpriseToEbitda")),
            "ev_revenue": number(quote.get("enterpriseToRevenue")),
            "dividend_yield": dividend_yield * 100 if dividend_yield is not None else None,
            "price": price,
        }
    except Exception:
        return {
            **item,
            "market_cap": None, "market_cap_cr": None, "pe": None, "pb": None,
            "peg": None, "roe": None, "roa": None, "debt_equity": None,
            "current_ratio": None, "ev_ebitda": None, "ev_revenue": None,
            "dividend_yield": None, "price": None,
        }


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
        items = [item for item in items if q in item["symbol"].lower() or q in item["name"].lower()]

    # Each worker gets its own HTTP client/session. This avoids sharing a
    # curl_cffi session across threads while allowing the external requests to
    # overlap. Results are restored to the original universe order below.
    def fetch_one(item: dict[str, Any]) -> dict[str, Any]:
        worker_client = YahooFinanceClient(client.settings)
        return _fetch_stock(worker_client, item)

    indexed_results: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(SCREENING_MAX_WORKERS, max(1, len(items)))) as executor:
        futures = {
            executor.submit(fetch_one, item): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                indexed_results[index] = future.result()
            except Exception:
                item = items[index]
                indexed_results[index] = {
                    **item,
                    "market_cap": None, "market_cap_cr": None, "pe": None, "pb": None,
                    "peg": None, "roe": None, "roa": None, "debt_equity": None,
                    "current_ratio": None, "ev_ebitda": None, "ev_revenue": None,
                    "dividend_yield": None, "price": None,
                }

    stocks = [indexed_results[index] for index in range(len(items))]

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
        "sectors": nifty_sectors(),
    }
