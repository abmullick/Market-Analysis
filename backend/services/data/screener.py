from __future__ import annotations

import re
import time
from typing import Any

import curl_cffi.requests
from bs4 import BeautifulSoup


class ScreenerFinanceError(Exception):
    """Screener.in data retrieval error."""


class ScreenerFinanceClient:
    """Read Indian-equity fundamentals from public Screener.in pages.

    Screener reports Indian financial statements in Rs. Crores and ratios such
    as ROE, ROCE and dividend yield in percentage points. The rest of the
    application normalises percentages as fractions before displaying them,
    so this adapter converts percentage-point values to fractions at the
    boundary and converts statement values from Crores to rupees.
    """

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
            "Cache-Control": "no-cache",
        })
        self._cache: dict[str, tuple[float, BeautifulSoup]] = {}

    @staticmethod
    def _symbol(symbol: str) -> str:
        return symbol.strip().upper().removesuffix(".NS").removesuffix(".BO")

    @staticmethod
    def _num(text: str | None) -> float | None:
        if text is None:
            return None
        value = text.strip().replace(",", "")
        value = value.replace("₹", "").replace("$", "")
        value = value.replace("€", "").replace("£", "")
        value = value.replace("%", "").replace("Cr.", "").replace("Cr", "")
        value = value.strip()
        if value in {"", "-", "--", "N/A", "NA"}:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _pct(value: float | None) -> float | None:
        """Convert Screener percentage points to a decimal fraction."""
        return value / 100 if value is not None else None

    @staticmethod
    def _cr(value: float | None) -> float | None:
        """Convert Rs. Crores to rupees."""
        return value * 1e7 if value is not None else None

    def _fetch(self, symbol: str) -> BeautifulSoup:
        key = self._symbol(symbol)
        cached = self._cache.get(key)
        if cached and time.time() - cached[0] < self.CACHE_TTL:
            return cached[1]

        last_error: Exception | None = None
        for path in (f"/{key}/consolidated/", f"/{key}/"):
            for attempt in range(3):
                try:
                    response = self.session.get(
                        f"{self.BASE_URL}{path}",
                        timeout=25,
                        allow_redirects=True,
                    )
                    if response.status_code == 429:
                        last_error = ScreenerFinanceError(
                            "Screener.in HTTP 429 Too Many Requests"
                        )
                        if attempt < 2:
                            time.sleep(1.0 + attempt)
                            continue
                        break

                    response.raise_for_status()
                    text = response.text
                    if "Company not found" in text or "Page not found" in text:
                        last_error = ScreenerFinanceError(
                            f"Screener.in company not found: {key}"
                        )
                        break

                    soup = BeautifulSoup(text, "html.parser")
                    if not soup.select_one("#top-ratios"):
                        last_error = ScreenerFinanceError(
                            f"Screener.in returned no company data for {key}"
                        )
                        break

                    self._cache[key] = (time.time(), soup)
                    return soup
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(0.5 + attempt * 0.5)

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
                result[name.get_text(" ", strip=True)] = cls._num(
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

        headers = [th.get_text(" ", strip=True) for th in table.select("thead th")][1:]
        rows: dict[str, list[float | None]] = {}
        for tr in table.select("tbody tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            label = cells[0].get_text(" ", strip=True)
            rows[label] = [cls._num(c.get_text(" ", strip=True)) for c in cells[1:]]
        return headers, rows

    @staticmethod
    def _annual_indices(headers: list[str]) -> list[int]:
        return [
            i for i, header in enumerate(headers)
            if re.fullmatch(r"Mar \d{4}", header)
        ]

    @staticmethod
    def _ttm_index(headers: list[str]) -> int | None:
        for i, header in enumerate(headers):
            if header.upper() == "TTM":
                return i
        return None

    @staticmethod
    def _row(
        rows: dict[str, list[float | None]],
        labels: list[str],
        index: int,
    ) -> float | None:
        for label in labels:
            values = rows.get(label)
            if values is not None and index < len(values) and values[index] is not None:
                return values[index]
        return None

    @classmethod
    def _annual_rows(
        cls,
        headers: list[str],
        rows: dict[str, list[float | None]],
        mapping: dict[str, tuple[str, bool]],
        derived: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for index in cls._annual_indices(headers):
            period = headers[index]
            row: dict[str, Any] = {
                "asOfDate": f"{period[-4:]}-03-31",
                "periodType": "12M",
            }
            for source_label, (target, crore) in mapping.items():
                value = cls._row(rows, [source_label], index)
                if value is not None:
                    row[target] = {"raw": cls._cr(value) if crore else value}
            if derived:
                for target, builder in derived.items():
                    value = builder(index, rows)
                    if value is not None:
                        row[target] = {"raw": value}
            output.append(row)
        return output

    def quote_summary(self, symbol: str) -> dict[str, Any]:
        soup = self._fetch(symbol)
        ratios = self._top_ratios(soup)
        heading = soup.find("h1")
        name = heading.get_text(" ", strip=True) if heading else self._symbol(symbol)

        price = ratios.get("Current Price")
        market_cap_cr = ratios.get("Market Cap")
        book_value = ratios.get("Book Value")

        pl_headers, pl_rows = self._table(soup, "profit-loss")
        annual = self._annual_indices(pl_headers)
        latest = annual[-1] if annual else None
        ttm = self._ttm_index(pl_headers)

        latest_sales = self._row(pl_rows, ["Sales", "Sales +"], latest) if latest is not None else None
        latest_op = self._row(pl_rows, ["Operating Profit"], latest) if latest is not None else None
        latest_profit = self._row(pl_rows, ["Net Profit", "Net Profit +"], latest) if latest is not None else None
        latest_dep = self._row(pl_rows, ["Depreciation"], latest) if latest is not None else None
        latest_eps = self._row(pl_rows, ["EPS in Rs"], latest) if latest is not None else None
        latest_payout = self._row(pl_rows, ["Dividend Payout %"], latest) if latest is not None else None

        ttm_sales = self._row(pl_rows, ["Sales", "Sales +"], ttm) if ttm is not None else latest_sales
        ttm_op = self._row(pl_rows, ["Operating Profit"], ttm) if ttm is not None else latest_op
        ttm_profit = self._row(pl_rows, ["Net Profit", "Net Profit +"], ttm) if ttm is not None else latest_profit
        ttm_dep = self._row(pl_rows, ["Depreciation"], ttm) if ttm is not None else latest_dep
        ttm_eps = self._row(pl_rows, ["EPS in Rs"], ttm) if ttm is not None else latest_eps

        balance_headers, balance_rows = self._table(soup, "balance-sheet")
        balance_annual = self._annual_indices(balance_headers)
        balance_latest = balance_annual[-1] if balance_annual else None
        debt_cr = self._row(balance_rows, ["Borrowings", "Borrowings +"], balance_latest) if balance_latest is not None else None
        equity_capital_cr = self._row(balance_rows, ["Equity Capital"], balance_latest) if balance_latest is not None else None
        reserves_cr = self._row(balance_rows, ["Reserves"], balance_latest) if balance_latest is not None else None
        assets_cr = self._row(balance_rows, ["Total Assets"], balance_latest) if balance_latest is not None else None
        liabilities_cr = self._row(balance_rows, ["Total Liabilities"], balance_latest) if balance_latest is not None else None

        equity_cr = None
        if equity_capital_cr is not None or reserves_cr is not None:
            equity_cr = (equity_capital_cr or 0) + (reserves_cr or 0)

        market_cap = self._cr(market_cap_cr)
        debt = self._cr(debt_cr)
        equity = self._cr(equity_cr)
        shares = market_cap / price if market_cap is not None and price not in (None, 0) else None

        pb = price / book_value if price is not None and book_value not in (None, 0) else None
        debt_equity = debt_cr / equity_cr if debt_cr is not None and equity_cr not in (None, 0) else None

        annual_ebitda = (latest_op or 0) + (latest_dep or 0) if latest_op is not None or latest_dep is not None else None
        ttm_ebitda = (ttm_op or 0) + (ttm_dep or 0) if ttm_op is not None or ttm_dep is not None else None

        enterprise_value = None
        if market_cap is not None and debt is not None:
            enterprise_value = market_cap + debt

        data: dict[str, Any] = {
            "longName": name,
            "shortName": name,
            "exchangeName": "NSE",
            "fullExchangeName": "National Stock Exchange of India",
            "currency": "INR",
            "country": "India",
            "regularMarketPrice": price,
            "marketCap": market_cap,
            "enterpriseValue": enterprise_value,
            "sharesOutstanding": shares,
            "trailingPE": ratios.get("Stock P/E"),
            "priceToBook": pb,
            "priceToSalesTrailing12Months": (
                market_cap_cr / ttm_sales if market_cap_cr is not None and ttm_sales not in (None, 0) else None
            ),
            "dividendYield": cls._pct(ratios.get("Dividend Yield")),
            "returnOnEquity": cls._pct(ratios.get("ROE")),
            "returnOnAssets": None,
            "returnOnCapitalEmployed": cls._pct(ratios.get("ROCE")),
            "debtToEquity": debt_equity,
            "sector": None,
            "industry": None,
            "_source": "Screener.in",
            "totalRevenue": self._cr(ttm_sales),
            "netIncomeToCommon": self._cr(ttm_profit),
            "trailingEps": ttm_eps,
            "ebitda": self._cr(ttm_ebitda),
            "operatingCashflow": None,
            "freeCashflow": None,
            "capitalExpenditure": None,
            "totalCash": None,
            "totalDebt": debt,
            "totalAssets": self._cr(assets_cr),
            "totalLiabilities": self._cr(liabilities_cr),
            "operatingMargins": (
                self._pct(ttm_op / ttm_sales * 100)
                if ttm_op is not None and ttm_sales not in (None, 0) else None
            ),
            "profitMargins": (
                self._pct(ttm_profit / ttm_sales * 100)
                if ttm_profit is not None and ttm_sales not in (None, 0) else None
            ),
            "payoutRatio": self._pct(latest_payout),
        }

        previous = annual[-2] if len(annual) >= 2 else None
        if latest is not None and previous is not None:
            previous_sales = self._row(pl_rows, ["Sales", "Sales +"], previous)
            previous_profit = self._row(pl_rows, ["Net Profit", "Net Profit +"], previous)
            previous_eps = self._row(pl_rows, ["EPS in Rs"], previous)
            if latest_sales is not None and previous_sales not in (None, 0):
                data["revenueGrowth"] = self._pct((latest_sales / previous_sales - 1) * 100)
            if latest_profit is not None and previous_profit not in (None, 0):
                data["earningsGrowth"] = self._pct((latest_profit / previous_profit - 1) * 100)
            if latest_eps is not None and previous_eps not in (None, 0):
                data["earningsQuarterlyGrowth"] = self._pct((latest_eps / previous_eps - 1) * 100)

        # Keep the annual ratio section authoritative when available.
        ratio_headers, ratio_rows = self._table(soup, "ratios")
        ratio_annual = self._annual_indices(ratio_headers)
        if ratio_annual:
            ri = ratio_annual[-1]
            roe = self._row(ratio_rows, ["ROE %"], ri)
            roce = self._row(ratio_rows, ["ROCE %"], ri)
            opm = self._row(ratio_rows, ["OPM %"], ri)
            if roe is not None:
                data["returnOnEquity"] = self._pct(roe)
            if roce is not None:
                data["returnOnCapitalEmployed"] = self._pct(roce)
            if opm is not None:
                data["operatingMargins"] = self._pct(opm)

        return data

    def financial_history(
        self,
        symbol: str,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        soup = self._fetch(symbol)
        income_headers, income = self._table(soup, "profit-loss")
        balance_headers, balance = self._table(soup, "balance-sheet")
        cash_headers, cash = self._table(soup, "cash-flow")

        def value(rows: dict[str, list[float | None]], labels: list[str], index: int) -> float | None:
            return self._row(rows, labels, index)

        income_rows: list[dict[str, Any]] = []
        for index in self._annual_indices(income_headers):
            period = income_headers[index]
            sales = value(income, ["Sales", "Sales +"], index)
            op = value(income, ["Operating Profit"], index)
            dep = value(income, ["Depreciation"], index)
            profit = value(income, ["Net Profit", "Net Profit +"], index)
            eps = value(income, ["EPS in Rs"], index)
            row: dict[str, Any] = {
                "asOfDate": f"{period[-4:]}-03-31",
                "periodType": "12M",
            }
            if sales is not None:
                row["annualTotalRevenue"] = {"raw": self._cr(sales)}
            if op is not None:
                row["annualOperatingIncome"] = {"raw": self._cr(op)}
            if dep is not None and op is not None:
                row["annualEBITDA"] = {"raw": self._cr(op + dep)}
            if profit is not None:
                row["annualNetIncome"] = {"raw": self._cr(profit)}
            if eps is not None:
                row["annualDilutedEPS"] = {"raw": eps}
            income_rows.append(row)

        balance_rows: list[dict[str, Any]] = []
        for index in self._annual_indices(balance_headers):
            period = balance_headers[index]
            equity_capital = value(balance, ["Equity Capital"], index)
            reserves = value(balance, ["Reserves"], index)
            debt = value(balance, ["Borrowings", "Borrowings +"], index)
            assets = value(balance, ["Total Assets"], index)
            liabilities = value(balance, ["Total Liabilities"], index)
            row = {
                "asOfDate": f"{period[-4:]}-03-31",
                "periodType": "12M",
            }
            if equity_capital is not None or reserves is not None:
                row["annualStockholdersEquity"] = {
                    "raw": self._cr((equity_capital or 0) + (reserves or 0))
                }
            if debt is not None:
                row["annualTotalDebt"] = {"raw": self._cr(debt)}
            if assets is not None:
                row["annualTotalAssets"] = {"raw": self._cr(assets)}
            if liabilities is not None:
                row["annualTotalLiabilitiesNetMinorityInterest"] = {
                    "raw": self._cr(liabilities)
                }
            balance_rows.append(row)

        cash_rows: list[dict[str, Any]] = []
        for index in self._annual_indices(cash_headers):
            period = cash_headers[index]
            cfo = value(cash, ["Cash from Operating Activity +", "Cash from Operating Activity"], index)
            fcf = value(cash, ["Free Cash Flow"], index)
            row = {
                "asOfDate": f"{period[-4:]}-03-31",
                "periodType": "12M",
            }
            if cfo is not None:
                row["annualOperatingCashFlow"] = {"raw": self._cr(cfo)}
            if fcf is not None:
                row["annualFreeCashFlow"] = {"raw": self._cr(fcf)}
            cash_rows.append(row)

        return {
            "income": {
                "annualTotalRevenue": income_rows,
                "annualOperatingIncome": income_rows,
                "annualEBITDA": income_rows,
                "annualNetIncome": income_rows,
                "annualDilutedEPS": income_rows,
            },
            "balance": {
                "annualTotalAssets": balance_rows,
                "annualTotalLiabilitiesNetMinorityInterest": balance_rows,
                "annualStockholdersEquity": balance_rows,
                "annualTotalDebt": balance_rows,
            },
            "cash": {
                "annualOperatingCashFlow": cash_rows,
                "annualFreeCashFlow": cash_rows,
            },
        }
