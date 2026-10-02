from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from backend.models.fundamentals import FinancialPeriod, Fundamentals
from backend.services.data.yahoo import YahooFinanceClient, number
from backend.services.stocks.screener import ScreenerEngine


def field(raw: dict[str, Any], name: str) -> Optional[float]:
    return number(raw.get(name))


def percentage(raw: dict[str, Any], name: str) -> Optional[float]:
    value = number(raw.get(name))
    if value is None:
        return None
    return value * 100 if abs(value) <= 5 else value


def historical_date(row: dict[str, Any]) -> str:
    return str(row.get("asOfDate") or row.get("periodEnd") or "")[:10]


def historical_value(row: dict[str, Any], key: str) -> Optional[float]:
    value = row.get("reportedValue")
    if isinstance(value, dict):
        value = value.get("raw")
    if value is None:
        value = row.get(key)
    return number(value)


def extract_series(rows: list[dict[str, Any]], key: str) -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []
    for row in rows:
        date = historical_date(row)
        value = historical_value(row, key)
        if date and value is not None:
            result.append((date, value))
    return sorted({date: value for date, value in result}.items())


def cagr(series: list[tuple[str, float]], years: int) -> Optional[float]:
    series = sorted((d, v) for d, v in series if d and v is not None)
    if len(series) < 2 or series[-1][1] <= 0:
        return None
    end_date, end_value = series[-1]
    target_year = int(end_date[:4]) - years
    candidates = [(d, v) for d, v in series[:-1] if int(d[:4]) <= target_year]
    if not candidates:
        return None
    start_date, start_value = candidates[-1]
    actual_years = int(end_date[:4]) - int(start_date[:4])
    if start_value <= 0 or actual_years < years or actual_years <= 0:
        return None
    return (end_value / start_value) ** (1 / actual_years) - 1


def build_periods(data: dict[str, list[dict[str, Any]]], keys: list[str]) -> list[FinancialPeriod]:
    periods: dict[str, dict[str, Optional[float]]] = defaultdict(dict)
    for key in keys:
        for row in data.get(key, []):
            date = historical_date(row)
            value = historical_value(row, key)
            if date and value is not None:
                periods[date][key.removeprefix("annual")] = value
    return [FinancialPeriod(period=p, values=v) for p, v in sorted(periods.items(), reverse=True)]


def normalize(symbol: str, raw: dict[str, Any], history: dict[str, Any]) -> Fundamentals:
    revenue = extract_series(history["income"].get("annualTotalRevenue", []), "annualTotalRevenue")
    profit = extract_series(history["income"].get("annualNetIncome", []), "annualNetIncome")
    eps = extract_series(history["income"].get("annualDilutedEPS", []), "annualDilutedEPS")
    fcf = extract_series(history["cash"].get("annualFreeCashFlow", []), "annualFreeCashFlow")
    operating = extract_series(history["income"].get("annualOperatingIncome", []), "annualOperatingIncome")
    revenue_map = dict(revenue)
    margin_series = [(d, op / revenue_map[d] * 100) for d, op in operating if d in revenue_map and revenue_map[d] != 0]
    margin_change = margin_series[-1][1] - margin_series[0][1] if len(margin_series) >= 2 else None

    return Fundamentals(
        symbol=symbol.upper(), name=raw.get("longName") or raw.get("shortName"),
        exchange=raw.get("exchangeName") or raw.get("fullExchangeName"), currency=raw.get("currency"),
        sector=raw.get("sector"), industry=raw.get("industry"), country=raw.get("country"),
        price=field(raw, "regularMarketPrice"), market_cap=field(raw, "marketCap"), enterprise_value=field(raw, "enterpriseValue"),
        shares_outstanding=field(raw, "sharesOutstanding"), beta=field(raw, "beta"),
        pe=field(raw, "trailingPE"), forward_pe=field(raw, "forwardPE"), pb=field(raw, "priceToBook"),
        ps=field(raw, "priceToSalesTrailing12Months"), peg=field(raw, "pegRatio"), ev_ebitda=field(raw, "enterpriseToEbitda"),
        ev_revenue=field(raw, "enterpriseToRevenue"), dividend_yield=percentage(raw, "dividendYield"), payout_ratio=percentage(raw, "payoutRatio"),
        roe=percentage(raw, "returnOnEquity"), roa=percentage(raw, "returnOnAssets"), roce=percentage(raw, "returnOnCapitalEmployed"),
        profit_margin=percentage(raw, "profitMargins"), operating_margin=percentage(raw, "operatingMargins"), gross_margin=percentage(raw, "grossMargins"),
        debt_equity=field(raw, "debtToEquity"), current_ratio=field(raw, "currentRatio"), quick_ratio=field(raw, "quickRatio"),
        revenue=field(raw, "totalRevenue"), operating_profit=field(raw, "operatingProfit"), ebitda=field(raw, "ebitda"),
        net_profit=field(raw, "netIncomeToCommon"), eps=field(raw, "trailingEps"), operating_cash_flow=field(raw, "operatingCashflow"),
        capital_expenditure=field(raw, "capitalExpenditure"), free_cash_flow=field(raw, "freeCashflow"), cash=field(raw, "totalCash"),
        total_debt=field(raw, "totalDebt"), revenue_growth=percentage(raw, "revenueGrowth"), profit_growth=percentage(raw, "earningsGrowth"),
        eps_growth=percentage(raw, "earningsQuarterlyGrowth"), revenue_cagr_3y=cagr(revenue, 3), revenue_cagr_5y=cagr(revenue, 5),
        profit_cagr_3y=cagr(profit, 3), profit_cagr_5y=cagr(profit, 5), eps_cagr_3y=cagr(eps, 3), eps_cagr_5y=cagr(eps, 5),
        fcf_cagr_3y=cagr(fcf, 3), fcf_cagr_5y=cagr(fcf, 5), operating_margin_change=margin_change,
        data_as_of=datetime.utcnow().date().isoformat(), source=raw.get("_source") or "Fundamentals provider",
    )


def get_stock_analysis(client: YahooFinanceClient, symbol: str) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    raw = client.quote_summary(symbol)
    history = client.financial_history(symbol)
    fundamentals = normalize(symbol, raw, history)

    if fundamentals.peg is None and fundamentals.pe is not None and fundamentals.eps_cagr_3y and fundamentals.eps_cagr_3y > 0:
        fundamentals.peg = fundamentals.pe / (fundamentals.eps_cagr_3y * 100)

    income_keys = ["annualTotalRevenue", "annualGrossProfit", "annualOperatingIncome", "annualEBITDA", "annualNetIncome", "annualDilutedEPS", "annualOperatingCashFlow"]
    balance_keys = [
        "annualTotalAssets", "annualTotalLiabilitiesNetMinorityInterest", "annualStockholdersEquity", "annualTotalDebt",
        "annualCurrentAssets", "annualCurrentLiabilities", "annualNetBlock", "annualDebtors", "annualInventory", "annualTradePayables",
    ]
    cash_keys = ["annualOperatingCashFlow", "annualCapitalExpenditure", "annualFreeCashFlow"]

    result = {
        "fundamentals": fundamentals.model_dump(),
        "income_statement": [item.model_dump() for item in build_periods(history["income"], income_keys)],
        "balance_sheet": [item.model_dump() for item in build_periods(history["balance"], balance_keys)],
        "cash_flow": [item.model_dump() for item in build_periods(history["cash"], cash_keys)],
        "warnings": [
            "Indian equity fundamentals are sourced from Screener.in when available; individual fields may be unavailable or revised.",
            "Derived metrics are calculated from the underlying annual statements and may differ from Screener's displayed ratios when definitions differ.",
            "CAGR metrics require the requested lookback period and a positive starting value.",
        ],
    }
    result["derived_analysis"] = ScreenerEngine().derive_fundamental_metrics(result)
    return result
