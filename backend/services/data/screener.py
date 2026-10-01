from __future__ import annotations

import re
import time
from typing import Any

import curl_cffi.requests
from bs4 import BeautifulSoup


class ScreenerFinanceError(Exception):
    """Screener.in data retrieval error."""


class ScreenerFinanceClient:
    """Small, cached reader for public Screener.in company pages.

    This is used as the Indian-equity fundamentals fallback because Yahoo's
    cookie/crumb endpoint is frequently rate-limited from cloud datacenter IPs.
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
        })
        self._cache: dict[str, tuple[float, BeautifulSoup]] = {}

    @staticmethod
    def _symbol(symbol: str) -> str:
        return symbol.strip().upper().removesuffix(".NS").removesuffix(".BO")

    @staticmethod
    def _num(text: str | None) -> float | None:
        if not text:
            return None
        value = text.strip().replace(",", "")
        value = re.sub(r"[₹$€£]", "", value)
        value = value.replace("Cr.", "").replace("Cr", "")
        value = value.replace("%", "").strip()
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
                if "Company not found" in response.text or "Page not found" in response.text:
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

    @staticmethod
    def _top_ratios(soup: BeautifulSoup) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for item in soup.select("#top-ratios li"):
            name = item.select_one(".name")
            value = item.select_one(".number")
            if name and value:
                result[name.get_text(" ", strip=True)] = ScreenerFinanceClient._num(
                    value.get_text(" ", strip=True)
                )
        return result

    @staticmethod
    def _table(
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
                ScreenerFinanceClient._num(c.get_text(" ", strip=True))
                for c in cells[1:]
            ]
        return headers, rows

    @staticmethod
    def _annual_rows(
        headers: list[str],
        rows: dict[str, list[float | None]],
        mapping: dict[str, str],
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for index, period in enumerate(headers):
            if not period.startswith("Mar "):
                continue
            row: dict[str, Any] = {
                "asOfDate": f"{period[-4:]}-03-31",
                "periodType": "12M",
            }
            for source, target in mapping.items():
                values = rows.get(source, [])
                if index < len(values) and values[index] is not None:
                    row[target] = {"raw": values[index]}
            output.append(row)
        return output

    def quote_summary(self, symbol: str) -> dict[str, Any]:
        soup = self._fetch(symbol)
        ratios = self._top_ratios(soup)
        heading = soup.find("h1")
        name = heading.get_text(" ", strip=True) if heading else self._symbol(symbol)

        market_cap_cr = ratios.get("Market Cap")
        data: dict[str, Any] = {
            "longName": name,
            "shortName": name,
            "exchangeName": "NSE",
            "fullExchangeName": "National Stock Exchange of India",
            "currency": "INR",
            "country": "India",
            "regularMarketPrice": ratios.get("Current Price"),
            "marketCap": market_cap_cr * 1e7 if market_cap_cr is not None else None,
            "trailingPE": ratios.get("Stock P/E"),
            "priceToBook": None,
            "dividendYield": ratios.get("Dividend Yield"),
            "returnOnEquity": ratios.get("ROE"),
            "returnOnAssets": None,
            "sector": None,
            "industry": None,
            "_source": "Screener.in",
        }

        headers, rows = self._table(soup, "ratios")
        if headers:
            last = len(headers) - 1
            for label, key in {
                "ROE %": "returnOnEquity",
                "OPM %": "operatingMargins",
                "Debt to equity": "debtToEquity",
                "Current ratio": "currentRatio",
                "Quick ratio": "quickRatio",
            }.items():
                values = rows.get(label, [])
                if last < len(values) and values[last] is not None:
                    data[key] = values[last]

        return data

    def financial_history(
        self,
        symbol: str,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        soup = self._fetch(symbol)
        income_headers, income = self._table(soup, "profit-loss")
        balance_headers, balance = self._table(soup, "balance-sheet")
        cash_headers, cash = self._table(soup, "cash-flow")

        income_rows = self._annual_rows(income_headers, income, {
            "Sales": "annualTotalRevenue",
            "Operating Profit": "annualOperatingIncome",
            "Net Profit": "annualNetIncome",
            "EPS in Rs": "annualDilutedEPS",
        })
        balance_rows = self._annual_rows(balance_headers, balance, {
            "Total Assets": "annualTotalAssets",
            "Total Liabilities": "annualTotalLiabilitiesNetMinorityInterest",
            "Borrowings": "annualTotalDebt",
            "Cash": "annualCashCashEquivalentsAndShortTermInvestments",
        })
        cash_rows = self._annual_rows(cash_headers, cash, {
            "Cash from Operating Activity": "annualOperatingCashFlow",
            "Free Cash Flow": "annualFreeCashFlow",
        })

        # Screener statement values are in ₹ crore; the existing model stores
        # statement values in rupees, matching Yahoo's units.
        for rows in (income_rows, balance_rows, cash_rows):
            for row in rows:
                for key, value in row.items():
                    if key in {"asOfDate", "periodType"}:
                        continue
                    if isinstance(value, dict) and value.get("raw") is not None:
                        value["raw"] *= 1e7

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
