from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import curl_cffi.requests


YAHOO_CHART_HOSTS = (
    "https://query2.finance.yahoo.com",
    "https://query1.finance.yahoo.com",
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/154.0.0.0 Safari/537.36"
)


def _date(row: dict[str, Any]) -> str:
    return str(row.get("asOfDate") or row.get("periodEnd") or "")[:10]


def _value(row: dict[str, Any], key: str) -> float | None:
    value = row.get("reportedValue")
    if isinstance(value, dict):
        value = value.get("raw")
    if value is None:
        value = row.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _series(rows: list[dict[str, Any]], key: str) -> list[tuple[str, float]]:
    values: dict[str, float] = {}
    for row in rows:
        date = _date(row)
        value = _value(row, key)
        if date and value is not None:
            values[date] = value
    return sorted(values.items())


def _growth(series: list[tuple[str, float]]) -> list[dict[str, float | str | None]]:
    out: list[dict[str, float | str | None]] = []
    for index in range(1, len(series)):
        year = series[index][0][:4]
        previous = series[index - 1][1]
        current = series[index][1]
        growth = None
        if previous > 0 and current > 0:
            growth = (current / previous - 1) * 100
        out.append({"year": year, "value": growth})
    return out


def _trend(series: list[tuple[str, float]]) -> list[dict[str, float | str]]:
    return [{"year": date[:4], "value": value} for date, value in series]


def _rolling_cagr(prices: list[dict[str, Any]], years: int) -> list[dict[str, float | str | None]]:
    annual: dict[int, float] = {}
    for item in prices:
        try:
            year = int(str(item.get("date", ""))[:4])
            close = float(item.get("close"))
        except (TypeError, ValueError):
            continue
        if close > 0:
            annual[year] = close

    years_sorted = sorted(annual)
    out: list[dict[str, float | str | None]] = []
    for index in range(years, len(years_sorted)):
        end_year = years_sorted[index]
        start_year = years_sorted[index - years]
        start = annual[start_year]
        end = annual[end_year]
        value = (end / start) ** (1 / years) - 1 if start > 0 and end > 0 else None
        out.append({"year": str(end_year), "value": value * 100 if value is not None else None})
    return out


def _screener_price_cagr(growth: dict[str, dict[str, float | None]]) -> list[dict[str, float | str | None]]:
    values = growth.get("Stock Price CAGR", {})
    period_map = [("1 Year", "1Y"), ("3 Years", "3Y"), ("5 Years", "5Y"), ("10 Years", "10Y")]
    return [
        {"year": label, "value": values.get(period)}
        for period, label in period_map
        if values.get(period) is not None
    ]


def yahoo_annual_prices(symbol: str, years: int = 7) -> list[dict[str, Any]]:
    """Fetch monthly Yahoo prices and retain the last available close per year."""
    symbol = symbol.strip().upper()
    params = {
        "range": f"{max(1, years)}y",
        "interval": "1mo",
        "events": "div,splits",
        "includeAdjustedClose": "true",
    }
    session = curl_cffi.requests.Session(impersonate="chrome")
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    for host in YAHOO_CHART_HOSTS:
        try:
            response = session.get(
                f"{host}/v8/finance/chart/{symbol}",
                params=params,
                timeout=20,
                allow_redirects=True,
            )
            response.raise_for_status()
            result = (response.json().get("chart", {}).get("result") or [None])[0]
            if not result:
                continue
            timestamps = result.get("timestamp") or []
            quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
            closes = quote.get("close") or []
            annual: dict[str, dict[str, Any]] = {}
            for timestamp, close in zip(timestamps, closes):
                if close is None:
                    continue
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                annual[dt.strftime("%Y")] = {"date": dt.strftime("%Y-%m-%d"), "close": float(close)}
            return [annual[key] for key in sorted(annual)]
        except Exception:
            continue
    return []


def build_stock_charts(
    history: dict[str, dict[str, list[dict[str, Any]]]],
    prices: list[dict[str, Any]],
) -> dict[str, Any]:
    income = history.get("income", {})
    balance = history.get("balance", {})
    growth_tables = history.get("growth", {})

    revenue = _series(income.get("annualTotalRevenue", []), "annualTotalRevenue")
    profit = _series(income.get("annualNetIncome", []), "annualNetIncome")
    eps = _series(income.get("annualDilutedEPS", []), "annualDilutedEPS")
    equity = _series(balance.get("annualStockholdersEquity", []), "annualStockholdersEquity")

    equity_map = dict(equity)
    roe: list[tuple[str, float]] = []
    for date, profit_value in profit:
        closing = equity_map.get(date)
        if closing is None or closing == 0:
            continue
        previous = [value for d, value in equity if d < date]
        opening = previous[-1] if previous else closing
        average_equity = (opening + closing) / 2
        if average_equity != 0:
            roe.append((date, profit_value / average_equity * 100))

    screener_price = _screener_price_cagr(growth_tables)
    rolling_3y = _rolling_cagr(prices, 3)
    rolling_5y = _rolling_cagr(prices, 5)

    return {
        "eps_growth": _growth(eps),
        "revenue_growth": _growth(revenue),
        "roe_trend": _trend(roe),
        "price_cagr": screener_price,
        "price_cagr_3y": rolling_3y,
        "price_cagr_5y": rolling_5y,
    }
