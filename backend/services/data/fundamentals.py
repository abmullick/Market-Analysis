from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.models.fundamentals import FinancialPeriod
from backend.services.data.yahoo import YahooFinanceClient


def _raw(value: Any) -> Any:
    if isinstance(value, dict):
        if "raw" in value:
            return value["raw"]
        if "reportedValue" in value:
            return _raw(value["reportedValue"])
    return value


def _num(value: Any) -> float | None:
    value = _raw(value)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _pct(value: Any) -> float | None:
    value = _num(value)
    if value is None:
        return None
    return value * 100 if abs(value) <= 5 else value


def _field(module: dict[str, Any], name: str) -> Any:
    return _raw(module.get(name))


def _series(ts: dict[str, Any], name: str) -> list[tuple[str, float | None]]:
    results = ts.get("result") or []
    if not results:
        return []
    rows = results[0].get(name) or []
    output: list[tuple[str, float | None]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = row.get("asOfDate") or row.get("periodEnd")
        if not date:
            continue
        output.append((str(date)[:10], _num(row.get("reportedValue", row.get("value")))))
    return sorted(output)


def _cagr(series: list[tuple[str, float | None]], years: int) -> float | None:
    values = [(d, v) for d, v in series if v is not None and v > 0]
    if len(values) < 2:
        return None
    end_date, end_value = values[-1]
    end_year = int(end_date[:4])
    candidates = [(d, v) for d, v in values[:-1] if int(d[:4]) <= end_year - years]
    if not candidates:
        return None
    start_date, start_value = candidates[-1]
    actual_years = end_year - int(start_date[:4])
    if actual_years <= 0 or start_value is None:
        return None
    return (end_value / start_value) ** (1 / actual_years) - 1


def _periods(ts: dict[str, Any], names: list[str]) -> list[FinancialPeriod]:
    dates: dict[str, dict[str, float | None]] = {}
    for name in names:
        for date, value in _series(ts, name):
            dates.setdefault(date, {})[name.removeprefix("annual")] = value
    return [FinancialPeriod(period=d, values=v) for d, v in sorted(dates.items(), reverse=True)]


def build_analysis(client: YahooFinanceClient, symbol: str) -> dict[str, Any]:
    symbol = symbol.upper().strip()
    raw = client.quote_summary(symbol)
    price = raw.get("price", {}) if isinstance(raw.get("price"), dict) else {}
    detail = raw.get("summaryDetail", {}) if isinstance(raw.get("summaryDetail"), dict) else {}
    stats = raw.get("defaultKeyStatistics", {}) if isinstance(raw.get("defaultKeyStatistics"), dict) else {}
    financial = raw.get("financialData", {}) if isinstance(raw.get("financialData"), dict) else {}
    profile = raw.get("assetProfile", {}) if isinstance(raw.get("assetProfile"), dict) else {}

    history = client.fundamentals_timeseries(symbol, [
        "annualTotalRevenue", "annualGrossProfit", "annualOperatingIncome", "annualEBITDA",
        "annualNetIncome", "annualDilutedEPS", "annualOperatingCashFlow", "annualCapitalExpenditure",
        "annualFreeCashFlow", "annualTotalAssets", "annualTotalLiabilitiesNetMinorityInterest",
        "annualStockholdersEquity", "annualCashCashEquivalentsAndShortTermInvestments",
        "annualTotalDebt", "annualCurrentAssets", "annualCurrentLiabilities",
    ], years=6)

    revenue = _series(history, "annualTotalRevenue")
    profit = _series(history, "annualNetIncome")
    eps = _series(history, "annualDilutedEPS")
    fcf = _series(history, "annualFreeCashFlow")
    op = _series(history, "annualOperatingIncome")
    margin_series = [(d, o / r) for (d, r), (_, o) in zip(revenue, op) if r and o is not None]

    f = {
        "symbol": symbol,
        "name": _field(price, "longName") or _field(price, "shortName"),
        "exchange": _field(price, "exchangeName") or _field(price, "fullExchangeName"),
        "currency": _field(price, "currency"), "sector": profile.get("sector"),
        "industry": profile.get("industry"), "country": profile.get("country"),
        "market_cap": _num(_field(price, "marketCap")), "enterprise_value": _num(_field(stats, "enterpriseValue")),
        "shares_outstanding": _num(_field(stats, "sharesOutstanding")), "price": _num(_field(price, "regularMarketPrice")),
        "beta": _num(_field(stats, "beta")), "pe": _num(_field(detail, "trailingPE")),
        "forward_pe": _num(_field(detail, "forwardPE")), "pb": _num(_field(stats, "priceToBook")),
        "ps": _num(_field(detail, "priceToSalesTrailing12Months")), "peg": _num(_field(stats, "pegRatio")),
        "ev_ebitda": _num(_field(stats, "enterpriseToEbitda")), "ev_revenue": _num(_field(stats, "enterpriseToRevenue")),
        "roe": _pct(_field(financial, "returnOnEquity")), "roa": _pct(_field(financial, "returnOnAssets")),
        "gross_margin": _pct(_field(financial, "grossMargins")), "operating_margin": _pct(_field(financial, "operatingMargins")),
        "profit_margin": _pct(_field(financial, "profitMargins")), "debt_equity": _num(_field(financial, "debtToEquity")),
        "current_ratio": _num(_field(financial, "currentRatio")), "quick_ratio": _num(_field(financial, "quickRatio")),
        "cash": _num(_field(financial, "totalCash")), "total_debt": _num(_field(financial, "totalDebt")),
        "revenue": _num(_field(financial, "totalRevenue")), "ebitda": _num(_field(financial, "ebitda")),
        "net_profit": _num(_field(financial, "netIncomeToCommon")), "eps": _num(_field(stats, "trailingEps")),
        "operating_cash_flow": _num(_field(financial, "operatingCashflow")), "free_cash_flow": _num(_field(financial, "freeCashflow")),
        "revenue_growth": _pct(_field(financial, "revenueGrowth")), "profit_growth": _pct(_field(financial, "earningsGrowth")),
        "eps_growth": _pct(_field(financial, "earningsQuarterlyGrowth")),
        "revenue_cagr_3y": _cagr(revenue, 3), "revenue_cagr_5y": _cagr(revenue, 5),
        "profit_cagr_3y": _cagr(profit, 3), "profit_cagr_5y": _cagr(profit, 5),
        "eps_cagr_3y": _cagr(eps, 3), "eps_cagr_5y": _cagr(eps, 5),
        "fcf_cagr_3y": _cagr(fcf, 3), "fcf_cagr_5y": _cagr(fcf, 5),
        "operating_margin_change": (margin_series[-1][1] - margin_series[0][1]) * 100 if len(margin_series) >= 2 else None,
        "dividend_yield": _pct(_field(detail, "dividendYield")), "payout_ratio": _pct(_field(detail, "payoutRatio")),
        "data_as_of": datetime.now(timezone.utc).date().isoformat(), "source": "Yahoo Finance",
    }
    return {
        "fundamentals": f,
        "income_statement": [p.model_dump() for p in _periods(history, ["annualTotalRevenue", "annualGrossProfit", "annualOperatingIncome", "annualEBITDA", "annualNetIncome", "annualDilutedEPS", "annualOperatingCashFlow"])],
        "balance_sheet": [p.model_dump() for p in _periods(history, ["annualTotalAssets", "annualTotalLiabilitiesNetMinorityInterest", "annualStockholdersEquity", "annualCashCashEquivalentsAndShortTermInvestments", "annualTotalDebt", "annualCurrentAssets", "annualCurrentLiabilities"])],
        "cash_flow": [p.model_dump() for p in _periods(history, ["annualOperatingCashFlow", "annualCapitalExpenditure", "annualFreeCashFlow"])],
        "warnings": ["Yahoo Finance data may be delayed, missing, or revised.", "CAGR metrics use available annual periods and may use a shorter lookback when history is insufficient."],
    }
