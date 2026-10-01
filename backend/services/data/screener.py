from __future__ import annotations

import re
import time
from typing import Any

import curl_cffi.requests
from bs4 import BeautifulSoup


class ScreenerFinanceError(Exception):
    """Screener.in data retrieval error."""


class ScreenerFinanceClient:
    """Read Indian-equity fundamentals from public Screener.in pages."""

    BASE_URL = "https://www.screener.in/company"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
    CACHE_TTL = 300

    def __init__(self) -> None:
        self.session = curl_cffi.requests.Session(impersonate="chrome")
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.screener.in/",
        })
        self._cache: dict[str, tuple[float, BeautifulSoup]] = {}

    @staticmethod
    def _symbol(symbol: str) -> str:
        return (
            symbol.strip()
            .upper()
            .removesuffix(".NS")
            .removesuffix(".BO")
        )

    @staticmethod
    def _num(text: str | None) -> float | None:
        if not text:
            return None

        value = text.strip()
        value = value.replace(",", "")
        value = value.replace("₹", "")
        value = value.replace("$", "")
        value = value.replace("€", "")
        value = value.replace("£", "")
        value = value.replace("%", "")
        value = value.replace("Cr.", "")
        value = value.replace("Cr", "")
        value = value.strip()

        if value in {"", "-", "--", "N/A", "NA"}:
            return None

        try:
            return float(value)
        except ValueError:
            return None

    def _fetch(self, symbol: str) -> BeautifulSoup:
        key = self._symbol(symbol)

        cached = self._cache.get(key)
        if cached and time.time() - cached[0] < self.CACHE_TTL:
            return cached[1]

        last_error: Exception | None = None

        for path in (f"/{key}/consolidated/", f"/{key}/"):
            try:
                response = self.session.get(
                    f"{self.BASE_URL}{path}",
                    timeout=20,
                    allow_redirects=True,
                )

                if response.status_code == 429:
                    raise ScreenerFinanceError(
                        "Screener.in HTTP 429 Too Many Requests"
                    )

                response.raise_for_status()

                if (
                    "Company not found" in response.text
                    or "Page not found" in response.text
                ):
                    raise ScreenerFinanceError(
                        f"Screener.in company not found: {key}"
                    )

                soup = BeautifulSoup(response.text, "html.parser")

                if not soup.select_one("#top-ratios"):
                    raise ScreenerFinanceError(
                        f"Screener.in returned no company data for {key}"
                    )

                self._cache[key] = (time.time(), soup)
                return soup

            except Exception as exc:
                last_error = exc
                time.sleep(0.4)

        raise ScreenerFinanceError(
            str(last_error) if last_error else "Screener.in request failed"
        )

    @classmethod
    def _top_ratios(cls, soup: BeautifulSoup) -> dict[str, float | None]:
        result: dict[str, float | None] = {}

        for item in soup.select("#top-ratios li"):
            name = item.select_one(".name")
            value = item.select_one(".number")

            if name and value:
                key = name.get_text(" ", strip=True)
                result[key] = cls._num(
                    value.get_text(" ", strip=True)
                )

        return result

    @classmethod
    def _table(
        cls,
        soup: BeautifulSoup,
        section_id: str,
    ) -> tuple[list[str], dict[str, list[float | None]]]:

        section = soup.find("section", id=section_id)

        if section is None:
            return [], {}

        table = section.find("table")

        if table is None:
            return [], {}

        headers = [
            th.get_text(" ", strip=True)
            for th in table.select("thead th")
        ][1:]

        rows: dict[str, list[float | None]] = {}

        for tr in table.select("tbody tr"):
            cells = tr.find_all(["th", "td"])

            if not cells:
                continue

            label = cells[0].get_text(" ", strip=True)

            rows[label] = [
                cls._num(c.get_text(" ", strip=True))
                for c in cells[1:]
            ]

        return headers, rows

    @staticmethod
    def _latest_annual_index(headers: list[str]) -> int | None:
        """
        Select the latest Mar YYYY column.

        Screener tables normally end with TTM. We deliberately ignore TTM
        when building the annual financial statements.
        """

        annual = [
            (index, header)
            for index, header in enumerate(headers)
            if re.fullmatch(r"Mar \d{4}", header)
        ]

        if not annual:
            return None

        return annual[-1][0]

    @staticmethod
    def _row_value(
        rows: dict[str, list[float | None]],
        labels: list[str],
        index: int,
    ) -> float | None:

        for label in labels:
            values = rows.get(label)

            if values is not None and index < len(values):
                value = values[index]

                if value is not None:
                    return value

        return None

    @staticmethod
    def _cr(value: float | None) -> float | None:
        """Convert ₹ crore to ₹."""
        return value * 1e7 if value is not None else None

    @classmethod
    def _annual_rows(
        cls,
        headers: list[str],
        rows: dict[str, list[float | None]],
        mapping: dict[str, tuple[str, bool]],
    ) -> list[dict[str, Any]]:

        output: list[dict[str, Any]] = []

        for index, period in enumerate(headers):

            if not re.fullmatch(r"Mar \d{4}", period):
                continue

            row: dict[str, Any] = {
                "asOfDate": f"{period[-4:]}-03-31",
                "periodType": "12M",
            }

            for source_labels, (target, crore) in mapping.items():

                values = rows.get(source_labels, [])

                if index >= len(values):
                    continue

                value = values[index]

                if value is None:
                    continue

                if crore:
                    value = cls._cr(value)

                row[target] = {"raw": value}

            output.append(row)

        return output

    def quote_summary(self, symbol: str) -> dict[str, Any]:

        soup = self._fetch(symbol)
        ratios = self._top_ratios(soup)

        heading = soup.find("h1")
        name = (
            heading.get_text(" ", strip=True)
            if heading
            else self._symbol(symbol)
        )

        # Screener's top ratios are already expressed as:
        # Market Cap -> ₹ crore
        # Dividend Yield -> percentage
        # ROE -> percentage
        # P/E -> multiple
        market_cap_cr = ratios.get("Market Cap")

        data: dict[str, Any] = {
            "longName": name,
            "shortName": name,
            "exchangeName": "NSE",
            "fullExchangeName": "National Stock Exchange of India",
            "currency": "INR",
            "country": "India",

            "regularMarketPrice": ratios.get("Current Price"),

            "marketCap": self._cr(market_cap_cr),

            "trailingPE": ratios.get("Stock P/E"),

            "priceToBook": None,
            "priceToSalesTrailing12Months": None,

            "dividendYield": ratios.get("Dividend Yield"),

            "returnOnEquity": ratios.get("ROE"),
            "returnOnAssets": None,

            "returnOnCapitalEmployed": ratios.get("ROCE"),

            "sector": None,
            "industry": None,

            "_source": "Screener.in",
        }

        # ---------------------------------------------------------
        # Annual ratios
        # ---------------------------------------------------------

        ratio_headers, ratio_rows = self._table(
            soup,
            "ratios",
        )

        ratio_index = self._latest_annual_index(ratio_headers)

        if ratio_index is not None:

            roe = self._row_value(
                ratio_rows,
                ["ROE %"],
                ratio_index,
            )

            roce = self._row_value(
                ratio_rows,
                ["ROCE %"],
                ratio_index,
            )

            operating_margin = self._row_value(
                ratio_rows,
                ["OPM %"],
                ratio_index,
            )

            debt_equity = self._row_value(
                ratio_rows,
                ["Debt to equity"],
                ratio_index,
            )

            current_ratio = self._row_value(
                ratio_rows,
                ["Current ratio"],
                ratio_index,
            )

            quick_ratio = self._row_value(
                ratio_rows,
                ["Quick ratio"],
                ratio_index,
            )

            if roe is not None:
                data["returnOnEquity"] = roe

            if roce is not None:
                data["returnOnCapitalEmployed"] = roce

            if operating_margin is not None:
                data["operatingMargins"] = operating_margin

            if debt_equity is not None:
                data["debtToEquity"] = debt_equity

            if current_ratio is not None:
                data["currentRatio"] = current_ratio

            if quick_ratio is not None:
                data["quickRatio"] = quick_ratio

        # ---------------------------------------------------------
        # Profit & Loss
        # ---------------------------------------------------------

        pl_headers, pl_rows = self._table(
            soup,
            "profit-loss",
        )

        pl_index = self._latest_annual_index(pl_headers)

        if pl_index is not None:

            revenue_cr = self._row_value(
                pl_rows,
                ["Sales", "Sales +"],
                pl_index,
            )

            operating_profit_cr = self._row_value(
                pl_rows,
                ["Operating Profit"],
                pl_index,
            )

            net_profit_cr = self._row_value(
                pl_rows,
                ["Net Profit", "Net Profit +"],
                pl_index,
            )

            depreciation_cr = self._row_value(
                pl_rows,
                ["Depreciation"],
                pl_index,
            )

            eps = self._row_value(
                pl_rows,
                ["EPS in Rs"],
                pl_index,
            )

            payout = self._row_value(
                pl_rows,
                ["Dividend Payout %"],
                pl_index,
            )

            revenue = self._cr(revenue_cr)
            operating_profit = self._cr(operating_profit_cr)
            net_profit = self._cr(net_profit_cr)

            data["totalRevenue"] = revenue
            data["netIncomeToCommon"] = net_profit

            # EPS is already ₹/share.
            data["trailingEps"] = eps

            if revenue and operating_profit is not None:
                data["operatingMargins"] = (
                    operating_profit / revenue * 100
                )

            if revenue and net_profit is not None:
                data["profitMargins"] = (
                    net_profit / revenue * 100
                )

            if (
                operating_profit_cr is not None
                and depreciation_cr is not None
            ):
                data["ebitda"] = self._cr(
                    operating_profit_cr + depreciation_cr
                )

            if payout is not None:
                data["payoutRatio"] = payout

            # Latest annual growth versus previous annual column.
            previous_index = pl_index - 1

            previous_revenue = self._row_value(
                pl_rows,
                ["Sales", "Sales +"],
                previous_index,
            )

            previous_profit = self._row_value(
                pl_rows,
                ["Net Profit", "Net Profit +"],
                previous_index,
            )

            if (
                revenue_cr is not None
                and previous_revenue not in (None, 0)
            ):
                data["revenueGrowth"] = (
                    revenue_cr / previous_revenue - 1
                ) * 100

            if (
                net_profit_cr is not None
                and previous_profit not in (None, 0)
            ):
                data["earningsGrowth"] = (
                    net_profit_cr / previous_profit - 1
                ) * 100

        # ---------------------------------------------------------
        # Balance Sheet
        # ---------------------------------------------------------

        balance_headers, balance_rows = self._table(
            soup,
            "balance-sheet",
        )

        balance_index = self._latest_annual_index(balance_headers)

        if balance_index is not None:

            debt = self._row_value(
                balance_rows,
                ["Borrowings"],
                balance_index,
            )

            cash = self._row_value(
                balance_rows,
                ["Cash", "Cash & Bank"],
                balance_index,
            )

            assets = self._row_value(
                balance_rows,
                ["Total Assets"],
                balance_index,
            )

            liabilities = self._row_value(
                balance_rows,
                ["Total Liabilities"],
                balance_index,
            )

            if debt is not None:
                data["totalDebt"] = self._cr(debt)

            if cash is not None:
                data["totalCash"] = self._cr(cash)

            if assets is not None:
                data["totalAssets"] = self._cr(assets)

            if liabilities is not None:
                data["totalLiabilities"] = self._cr(
                    liabilities
                )

        # ---------------------------------------------------------
        # Cash Flow
        # ---------------------------------------------------------

        cash_headers, cash_rows = self._table(
            soup,
            "cash-flow",
        )

        cash_index = self._latest_annual_index(cash_headers)

        if cash_index is not None:

            operating_cf = self._row_value(
                cash_rows,
                ["Cash from Operating Activity", "Cash from Operating Activity +"],
                cash_index,
            )

            free_cash_flow = self._row_value(
                cash_rows,
                ["Free Cash Flow"],
                cash_index,
            )

            capex = self._row_value(
                cash_rows,
                ["Capital Expenditure", "Capital Expenditure +"],
                cash_index,
            )

            if operating_cf is not None:
                data["operatingCashflow"] = self._cr(
                    operating_cf
                )

            if free_cash_flow is not None:
                data["freeCashflow"] = self._cr(
                    free_cash_flow
                )

            if capex is not None:
                data["capitalExpenditure"] = self._cr(
                    capex
                )

        return data

    def financial_history(
        self,
        symbol: str,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:

        soup = self._fetch(symbol)

        income_headers, income = self._table(
            soup,
            "profit-loss",
        )

        balance_headers, balance = self._table(
            soup,
            "balance-sheet",
        )

        cash_headers, cash = self._table(
            soup,
            "cash-flow",
        )

        income_rows = self._annual_rows(
            income_headers,
            income,
            {
                "Sales +": ("annualTotalRevenue", True),
                "Sales": ("annualTotalRevenue", True),

                "Operating Profit": (
                    "annualOperatingIncome",
                    True,
                ),

                "Net Profit +": (
                    "annualNetIncome",
                    True,
                ),

                "Net Profit": (
                    "annualNetIncome",
                    True,
                ),

                # EPS is NOT crore.
                "EPS in Rs": (
                    "annualDilutedEPS",
                    False,
                ),
            },
        )

        balance_rows = self._annual_rows(
            balance_headers,
            balance,
            {
                "Total Assets": (
                    "annualTotalAssets",
                    True,
                ),

                "Total Liabilities": (
                    "annualTotalLiabilitiesNetMinorityInterest",
                    True,
                ),

                "Borrowings": (
                    "annualTotalDebt",
                    True,
                ),

                "Cash": (
                    "annualCashCashEquivalentsAndShortTermInvestments",
                    True,
                ),
            },
        )

        cash_rows = self._annual_rows(
            cash_headers,
            cash,
            {
                "Cash from Operating Activity +": (
                    "annualOperatingCashFlow",
                    True,
                ),

                "Cash from Operating Activity": (
                    "annualOperatingCashFlow",
                    True,
                ),

                "Free Cash Flow": (
                    "annualFreeCashFlow",
                    True,
                ),
            },
        )

        return {
            "income": {
                "annualTotalRevenue": income_rows,
                "annualOperatingIncome": income_rows,
                "annualNetIncome": income_rows,
                "annualDilutedEPS": income_rows,
            },

            "balance": {
                "annualTotalAssets": balance_rows,
                "annualTotalLiabilitiesNetMinorityInterest": balance_rows,
                "annualTotalDebt": balance_rows,
                "annualCashCashEquivalentsAndShortTermInvestments": balance_rows,
            },

            "cash": {
                "annualOperatingCashFlow": cash_rows,
                "annualFreeCashFlow": cash_rows,
            },
        }