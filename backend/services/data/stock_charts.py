from __future__ import annotations

from typing import Any


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
        if previous != 0 and (previous > 0 and current > 0):
            growth = (current / previous - 1) * 100
        out.append({"year": year, "value": growth})
    return out


def _trend(series: list[tuple[str, float]]) -> list[dict[str, float | str]]:
    return [
        {"year": date[:4], "value": value}
        for date, value in series
    ]


def _rolling_cagr(
    prices: list[dict[str, Any]],
    years: int,
) -> list[dict[str, float | str | None]]:
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


def build_stock_charts(
    history: dict[str, dict[str, list[dict[str, Any]]]],
    prices: list[dict[str, Any]],
) -> dict[str, Any]:
    income = history.get("income", {})
    balance = history.get("balance", {})

    revenue = _series(income.get("annualTotalRevenue", []), "annualTotalRevenue")
    profit = _series(income.get("annualNetIncome", []), "annualNetIncome")
    eps = _series(income.get("annualDilutedEPS", []), "annualDilutedEPS")
    equity = _series(balance.get("annualStockholdersEquity", []), "annualStockholdersEquity")

    # ROE is derived from annual net income and the average of opening/closing
    # equity. This is a historical trend indicator, not a replacement for the
    # provider's reported TTM ROE.
    equity_map = dict(equity)
    roe: list[tuple[str, float]] = []
    for date, profit_value in profit:
        closing = equity_map.get(date)
        if closing is None or closing == 0:
            continue
        previous_candidates = [
            (d, value)
            for d, value in equity
            if d < date
        ]
        opening = previous_candidates[-1][1] if previous_candidates else closing
        average_equity = (opening + closing) / 2
        if average_equity != 0:
            roe.append((date, profit_value / average_equity * 100))

    return {
        "eps_growth": _growth(eps),
        "revenue_growth": _growth(revenue),
        "roe_trend": _trend(roe),
        "price_cagr_3y": _rolling_cagr(prices, 3),
        "price_cagr_5y": _rolling_cagr(prices, 5),
    }
