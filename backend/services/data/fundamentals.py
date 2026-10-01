from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from backend.models.fundamentals import (
    FinancialPeriod,
    Fundamentals,
)

from backend.services.data.yahoo import (
    YahooFinanceClient,
    number,
)


def field(
    raw: dict[str, Any],
    name: str,
) -> Optional[float]:
    return number(raw.get(name))


def percentage(
    raw: dict[str, Any],
    name: str,
) -> Optional[float]:
    value = number(raw.get(name))

    if value is None:
        return None

    return value * 100 if abs(value) <= 5 else value


# ----------------------------------------------------------------------
# Yahoo historical data helpers
# ----------------------------------------------------------------------

def historical_date(
    row: dict[str, Any],
) -> str:
    return str(
        row.get("asOfDate")
        or row.get("periodEnd")
        or ""
    )[:10]


def historical_value(
    row: dict[str, Any],
    key: str,
) -> Optional[float]:
    """
    Yahoo fundamentals-timeseries records look like:

        {
            "asOfDate": "2026-03-31",
            "periodType": "12M",
            "currencyCode": "INR",
            "reportedValue": {
                "raw": 123456789,
                "fmt": "123.46B"
            }
        }
    """

    value = row.get("reportedValue")

    if isinstance(value, dict):
        value = value.get("raw")

    if value is None:
        value = row.get(key)

    return number(value)


def extract_series(
    rows: list[dict[str, Any]],
    key: str,
) -> list[tuple[str, float]]:
    result: list[tuple[str, float]] = []

    for row in rows:
        date = historical_date(row)

        if not date:
            continue

        value = historical_value(
            row,
            key,
        )

        if value is not None:
            result.append(
                (
                    date,
                    value,
                )
            )

    # Keep one value per financial year.
    deduped = {
        date: value
        for date, value in result
    }

    return sorted(
        deduped.items()
    )


# ----------------------------------------------------------------------
# CAGR
# ----------------------------------------------------------------------

def cagr(
    series: list[tuple[str, float]],
    years: int,
) -> Optional[float]:
    """
    Calculate CAGR only when the requested lookback is actually
    available.

    For example, a 3-year CAGR for FY2026 requires a starting
    observation from FY2023 or earlier.

    We deliberately do NOT substitute a shorter period. This prevents
    a 5-year CAGR from being incorrectly reported as a 3-year CAGR
    when only four annual observations are available.

    CAGR is also not meaningful when the starting value is <= 0.
    """

    series = sorted(
        [
            (date, value)
            for date, value in series
            if (
                date
                and value is not None
            )
        ]
    )

    if len(series) < 2:
        return None

    end_date, end_value = series[-1]

    if end_value <= 0:
        return None

    target_year = (
        int(end_date[:4])
        - years
    )

    # We need an observation at the requested year
    # or earlier.
    candidates = [
        (date, value)
        for date, value in series[:-1]
        if (
            int(date[:4])
            <= target_year
        )
    ]

    if not candidates:
        return None

    start_date, start_value = candidates[-1]

    if start_value <= 0:
        return None

    actual_years = (
        int(end_date[:4])
        - int(start_date[:4])
    )

    # Do not silently convert a requested 5-year CAGR
    # into a shorter-period CAGR.
    if actual_years < years:
        return None

    if actual_years <= 0:
        return None

    return (
        (
            end_value
            / start_value
        )
        ** (1 / actual_years)
        - 1
    )


# ----------------------------------------------------------------------
# Historical period builder
# ----------------------------------------------------------------------

def build_periods(
    data: dict[
        str,
        list[dict[str, Any]]
    ],
    keys: list[str],
) -> list[FinancialPeriod]:

    periods: dict[
        str,
        dict[str, Optional[float]]
    ] = defaultdict(dict)

    for key in keys:

        for row in data.get(
            key,
            [],
        ):

            date = historical_date(row)

            if not date:
                continue

            value = historical_value(
                row,
                key,
            )

            if value is None:
                continue

            periods[date][
                key.removeprefix("annual")
            ] = value

    return [
        FinancialPeriod(
            period=period,
            values=values,
        )
        for period, values
        in sorted(
            periods.items(),
            reverse=True,
        )
    ]


# ----------------------------------------------------------------------
# Normalize snapshot + historical metrics
# ----------------------------------------------------------------------

def normalize(
    symbol: str,
    raw: dict[str, Any],
    history: dict[str, Any],
) -> Fundamentals:

    revenue = extract_series(
        history["income"].get(
            "annualTotalRevenue",
            [],
        ),
        "annualTotalRevenue",
    )

    profit = extract_series(
        history["income"].get(
            "annualNetIncome",
            [],
        ),
        "annualNetIncome",
    )

    eps = extract_series(
        history["income"].get(
            "annualDilutedEPS",
            [],
        ),
        "annualDilutedEPS",
    )

    fcf = extract_series(
        history["cash"].get(
            "annualFreeCashFlow",
            [],
        ),
        "annualFreeCashFlow",
    )

    operating = extract_series(
        history["income"].get(
            "annualOperatingIncome",
            [],
        ),
        "annualOperatingIncome",
    )

    # --------------------------------------------------------------
    # Operating margin trend
    # --------------------------------------------------------------

    revenue_map = dict(revenue)

    margin_series: list[
        tuple[str, float]
    ] = []

    for (
        date,
        operating_profit,
    ) in operating:

        revenue_value = revenue_map.get(
            date
        )

        if (
            revenue_value is not None
            and revenue_value != 0
        ):
            margin_series.append(
                (
                    date,
                    (
                        operating_profit
                        / revenue_value
                    )
                    * 100,
                )
            )

    margin_change = None

    if len(margin_series) >= 2:

        margin_series.sort()

        margin_change = (
            margin_series[-1][1]
            - margin_series[0][1]
        )

    # --------------------------------------------------------------
    # Build normalized fundamentals
    # --------------------------------------------------------------

    return Fundamentals(

        symbol=symbol.upper(),

        name=(
            raw.get("longName")
            or raw.get("shortName")
        ),

        exchange=(
            raw.get("exchangeName")
            or raw.get("fullExchangeName")
        ),

        currency=raw.get(
            "currency"
        ),

        sector=raw.get(
            "sector"
        ),

        industry=raw.get(
            "industry"
        ),

        country=raw.get(
            "country"
        ),

        # ----------------------------------------------------------
        # Market data
        # ----------------------------------------------------------

        price=field(
            raw,
            "regularMarketPrice",
        ),

        market_cap=field(
            raw,
            "marketCap",
        ),

        enterprise_value=field(
            raw,
            "enterpriseValue",
        ),

        shares_outstanding=field(
            raw,
            "sharesOutstanding",
        ),

        beta=field(
            raw,
            "beta",
        ),

        # ----------------------------------------------------------
        # Valuation
        # ----------------------------------------------------------

        pe=field(
            raw,
            "trailingPE",
        ),

        forward_pe=field(
            raw,
            "forwardPE",
        ),

        pb=field(
            raw,
            "priceToBook",
        ),

        ps=field(
            raw,
            "priceToSalesTrailing12Months",
        ),

        peg=field(
            raw,
            "pegRatio",
        ),

        ev_ebitda=field(
            raw,
            "enterpriseToEbitda",
        ),

        ev_revenue=field(
            raw,
            "enterpriseToRevenue",
        ),

        dividend_yield=percentage(
            raw,
            "dividendYield",
        ),

        payout_ratio=percentage(
            raw,
            "payoutRatio",
        ),

        # ----------------------------------------------------------
        # Profitability
        # ----------------------------------------------------------

        roe=percentage(
            raw,
            "returnOnEquity",
        ),

        roa=percentage(
            raw,
            "returnOnAssets",
        ),

        profit_margin=percentage(
            raw,
            "profitMargins",
        ),

        operating_margin=percentage(
            raw,
            "operatingMargins",
        ),

        gross_margin=percentage(
            raw,
            "grossMargins",
        ),

        # ----------------------------------------------------------
        # Balance sheet
        # ----------------------------------------------------------

        debt_equity=field(
            raw,
            "debtToEquity",
        ),

        current_ratio=field(
            raw,
            "currentRatio",
        ),

        quick_ratio=field(
            raw,
            "quickRatio",
        ),

        # ----------------------------------------------------------
        # Latest financial data
        # ----------------------------------------------------------

        revenue=field(
            raw,
            "totalRevenue",
        ),

        operating_profit=field(
            raw,
            "operatingProfit",
        ),

        ebitda=field(
            raw,
            "ebitda",
        ),

        net_profit=field(
            raw,
            "netIncomeToCommon",
        ),

        eps=field(
            raw,
            "trailingEps",
        ),

        operating_cash_flow=field(
            raw,
            "operatingCashflow",
        ),

        free_cash_flow=field(
            raw,
            "freeCashflow",
        ),

        cash=field(
            raw,
            "totalCash",
        ),

        total_debt=field(
            raw,
            "totalDebt",
        ),

        # ----------------------------------------------------------
        # Growth
        # ----------------------------------------------------------

        revenue_growth=percentage(
            raw,
            "revenueGrowth",
        ),

        profit_growth=percentage(
            raw,
            "earningsGrowth",
        ),

        eps_growth=percentage(
            raw,
            "earningsQuarterlyGrowth",
        ),

        # ----------------------------------------------------------
        # Historical CAGR
        # ----------------------------------------------------------

        revenue_cagr_3y=cagr(
            revenue,
            3,
        ),

        revenue_cagr_5y=cagr(
            revenue,
            5,
        ),

        profit_cagr_3y=cagr(
            profit,
            3,
        ),

        profit_cagr_5y=cagr(
            profit,
            5,
        ),

        eps_cagr_3y=cagr(
            eps,
            3,
        ),

        eps_cagr_5y=cagr(
            eps,
            5,
        ),

        # FCF CAGR is intentionally calculated only when the
        # starting FCF is positive.
        fcf_cagr_3y=cagr(
            fcf,
            3,
        ),

        fcf_cagr_5y=cagr(
            fcf,
            5,
        ),

        # Difference in operating margin measured in
        # percentage points.
        operating_margin_change=margin_change,

        data_as_of=datetime.utcnow()
        .date()
        .isoformat(),
    )


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------

def get_stock_analysis(
    client: YahooFinanceClient,
    symbol: str,
) -> dict[str, Any]:

    symbol = (
        symbol
        .strip()
        .upper()
    )

    raw = client.quote_summary(
        symbol
    )

    history = client.financial_history(
        symbol
    )

    fundamentals = normalize(
        symbol,
        raw,
        history,
    )

    # --------------------------------------------------------------
    # Historical statement fields
    # --------------------------------------------------------------

    income_keys = [
        "annualTotalRevenue",
        "annualGrossProfit",
        "annualOperatingIncome",
        "annualEBITDA",
        "annualNetIncome",
        "annualDilutedEPS",
        "annualOperatingCashFlow",
    ]

    balance_keys = [
        "annualTotalAssets",
        "annualTotalLiabilitiesNetMinorityInterest",
        "annualStockholdersEquity",
        "annualCashCashEquivalentsAndShortTermInvestments",
        "annualTotalDebt",
        "annualCurrentAssets",
        "annualCurrentLiabilities",
    ]

    cash_keys = [
        "annualOperatingCashFlow",
        "annualCapitalExpenditure",
        "annualFreeCashFlow",
    ]

    return {

        "fundamentals":
            fundamentals.model_dump(),

        "income_statement": [
            item.model_dump()
            for item in build_periods(
                history["income"],
                income_keys,
            )
        ],

        "balance_sheet": [
            item.model_dump()
            for item in build_periods(
                history["balance"],
                balance_keys,
            )
        ],

        "cash_flow": [
            item.model_dump()
            for item in build_periods(
                history["cash"],
                cash_keys,
            )
        ],

        "warnings": [
            "Yahoo Finance data can be delayed, missing, revised, or unavailable for individual fields.",
            "CAGR metrics are returned only when the requested lookback period is actually available.",
            "CAGR is not calculated when the starting value is zero or negative.",
        ],
    }
