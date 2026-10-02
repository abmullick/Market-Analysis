from __future__ import annotations

import re
import time
from typing import Any

import curl_cffi.requests
from bs4 import BeautifulSoup

from backend.services.stocks.nifty_universe import load_nifty_total_market


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
            "Cache-Control": "no-cache",
        })
        self._cache: dict[str, tuple[float, BeautifulSoup]] = {}

    @staticmethod
    def _symbol(symbol: str) -> str:
        return symbol.strip().upper().removesuffix(".NS").removesuffix(".BO")

    @staticmethod
    def _normal_label(value: str) -> str:
        return re.sub(r"\s+", " ", value.replace("\xa0", " ").strip()).casefold()

    @staticmethod
    def _num(text: str | None) -> float | None:
        if text is None:
            return None
        value = (
            text.strip()
            .replace(",", "")
            .replace("₹", "")
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .replace("%", "")
            .replace("Cr.", "")
            .replace("Cr", "")
            .strip()
        )
        if value in {"", "-", "--", "N/A", "NA", "%"}:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _pct(value: float | None) -> float | None:
        return value / 100 if value is not None else None

    @staticmethod
    def _cr(value: float | None) -> float | None:
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
                        last_error = ScreenerFinanceError("Screener.in HTTP 429 Too Many Requests")
                        if attempt < 2:
                            time.sleep(1.0 + attempt)
                            continue
                        break
                    response.raise_for_status()
                    text = response.text
                    if "Company not found" in text or "Page not found" in text:
                        last_error = ScreenerFinanceError(f"Screener.in company not found: {key}")
                        break
                    soup = BeautifulSoup(text, "html.parser")
                    if not soup.select_one("#top-ratios"):
                        last_error = ScreenerFinanceError(f"Screener.in returned no company data for {key}")
                        break
                    self._cache[key] = (time.time(), soup)
                    return soup
                except Exception as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(0.5 + attempt * 0.5)

        raise ScreenerFinanceError(str(last_error) if last_error else "Screener.in request failed")

    @classmethod
    def _top_ratios(cls, soup: BeautifulSoup) -> dict[str, float | None]:
        result: dict[str, float | None] = {}
        for item in soup.select("#top-ratios li"):
            name = item.select_one(".name")
            value = item.select_one(".number")
            if name and value:
                result[name.get_text(" ", strip=True)] = cls._num(value.get_text(" ", strip=True))
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

        header_cells = table.select("thead th")
        if not header_cells:
            header_cells = table.find_all("th")
        headers = [th.get_text(" ", strip=True) for th in header_cells][1:]

        rows: dict[str, list[float | None]] = {}
        for tr in table.select("tbody tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            label = cells[0].get_text(" ", strip=True)
            values = [cls._num(c.get_text(" ", strip=True)) for c in cells[1:]]
            rows[label] = values
        return headers, rows

    @staticmethod
    def _annual_indices(headers: list[str]) -> list[int]:
        return [i for i, header in enumerate(headers) if re.fullmatch(r"Mar \d{4}", header)]

    @staticmethod
    def _ttm_index(headers: list[str]) -> int | None:
        for i, header in enumerate(headers):
            if header.upper() == "TTM":
                return i
        return None

    @classmethod
    def _row(
        cls,
        rows: dict[str, list[float | None]],
        labels: list[str],
        index: int | None,
    ) -> float | None:
        if index is None:
            return None

        wanted = [cls._normal_label(label).rstrip("+").strip() for label in labels]
        for actual, values in rows.items():
            actual_normal = cls._normal_label(actual).rstrip("+").strip()
            if actual_normal in wanted and index < len(values) and values[index] is not None:
                return values[index]

        # Screener occasionally changes a displayed label by adding a footnote,
        # plus sign or whitespace. Prefix matching is deliberately a fallback.
        for actual, values in rows.items():
            actual_normal = cls._normal_label(actual).rstrip("+").strip()
            if any(
                actual_normal.startswith(label) or label.startswith(actual_normal)
                for label in wanted
            ) and index < len(values) and values[index] is not None:
                return values[index]
        return None

    @classmethod
    def _growth_tables(cls, soup: BeautifulSoup) -> dict[str, dict[str, float | None]]:
        result: dict[str, dict[str, float | None]] = {}
        titles = {
            "Compounded Sales Growth": ["10 Years", "5 Years", "3 Years", "TTM"],
            "Compounded Profit Growth": ["10 Years", "5 Years", "3 Years", "TTM"],
            "Stock Price CAGR": ["10 Years", "5 Years", "3 Years", "1 Year"],
            "Return on Equity": ["10 Years", "5 Years", "3 Years", "Last Year"],
        }

        for table in soup.find_all("table"):
            text = table.get_text(" ", strip=True)
            for title, periods in titles.items():
                if title not in text or title in result:
                    continue
                values: dict[str, float | None] = {}
                for tr in table.find_all("tr"):
                    cells = tr.find_all(["th", "td"])
                    if len(cells) < 2:
                        continue
                    label = re.sub(r"\s+", " ", cells[0].get_text(" ", strip=True)).rstrip(":").strip()
                    if label in periods:
                        values[label] = cls._num(cells[1].get_text(" ", strip=True))
                if values:
                    result[title] = values
        return result

    @classmethod
    def _sector_for_symbol(cls, symbol: str) -> str | None:
        try:
            target = symbol.upper()
            for stock in load_nifty_total_market():
                if stock.get("symbol", "").upper() in {
                    target,
                    target.removesuffix(".NS").removesuffix(".BO"),
                }:
                    return stock.get("sector")
        except Exception:
            pass
        return None

    @staticmethod
    def _is_financial_company(sector: str | None) -> bool:
        return (sector or "").strip().lower() in {"financial services", "financials"}

    def _extract(self, symbol: str) -> tuple[BeautifulSoup, dict[str, Any]]:
        soup = self._fetch(symbol)
        ratios = self._top_ratios(soup)
        growth = self._growth_tables(soup)
        return soup, {"ratios": ratios, "growth": growth}

    def quote_summary(self, symbol: str) -> dict[str, Any]:
        soup, extracted = self._extract(symbol)
        ratios = extracted["ratios"]
        growth = extracted["growth"]
        heading = soup.find("h1")
        name = heading.get_text(" ", strip=True) if heading else self._symbol(symbol)

        sector = self._sector_for_symbol(symbol)
        is_financial = self._is_financial_company(sector)
        price = ratios.get("Current Price")
        market_cap_cr = ratios.get("Market Cap")
        book_value = ratios.get("Book Value")

        pl_headers, pl_rows = self._table(soup, "profit-loss")
        annual = self._annual_indices(pl_headers)
        latest = annual[-1] if annual else None
        ttm = self._ttm_index(pl_headers)
        revenue_labels = ["Revenue", "Revenue +", "Sales", "Sales +"]
        operating_labels = ["Operating Profit", "Financing Profit"]
        profit_labels = ["Net Profit", "Net Profit +", "Profit after tax"]

        latest_sales = self._row(pl_rows, revenue_labels, latest)
        latest_op = self._row(pl_rows, operating_labels, latest)
        latest_profit = self._row(pl_rows, profit_labels, latest)
        latest_dep = self._row(pl_rows, ["Depreciation"], latest)
        latest_eps = self._row(pl_rows, ["EPS in Rs"], latest)
        latest_payout = self._row(pl_rows, ["Dividend Payout %"], latest)
        ttm_sales = self._row(pl_rows, revenue_labels, ttm) or latest_sales
        ttm_op = self._row(pl_rows, operating_labels, ttm) or latest_op
        ttm_profit = self._row(pl_rows, profit_labels, ttm) or latest_profit
        ttm_dep = self._row(pl_rows, ["Depreciation"], ttm) or latest_dep
        ttm_eps = self._row(pl_rows, ["EPS in Rs"], ttm) or latest_eps

        eps_cagr_3y = None
        if len(annual) >= 4 and ttm_eps is not None:
            base_eps = self._row(pl_rows, ["EPS in Rs"], annual[-4])
            if base_eps is not None and base_eps > 0 and ttm_eps > 0:
                eps_cagr_3y = (ttm_eps / base_eps) ** (1 / 3) - 1

        balance_headers, balance_rows = self._table(soup, "balance-sheet")
        balance_annual = self._annual_indices(balance_headers)
        balance_latest = balance_annual[-1] if balance_annual else None
        debt_cr = self._row(balance_rows, ["Borrowings", "Borrowings +", "Borrowing"], balance_latest)
        equity_capital_cr = self._row(balance_rows, ["Equity Capital"], balance_latest)
        reserves_cr = self._row(balance_rows, ["Reserves"], balance_latest)
        assets_cr = self._row(balance_rows, ["Total Assets"], balance_latest)
        liabilities_cr = self._row(balance_rows, ["Total Liabilities"], balance_latest)
        current_assets_cr = self._row(balance_rows, ["Current Assets"], balance_latest)
        current_liabilities_cr = self._row(balance_rows, ["Current Liabilities"], balance_latest)
        equity_cr = ((equity_capital_cr or 0) + (reserves_cr or 0)) if (equity_capital_cr is not None or reserves_cr is not None) else None

        cash_headers, cash_rows = self._table(soup, "cash-flow")
        cash_annual = self._annual_indices(cash_headers)
        cash_latest = cash_annual[-1] if cash_annual else None
        cash_ttm = self._ttm_index(cash_headers)
        cash_index = cash_ttm if cash_ttm is not None else cash_latest
        operating_cashflow_cr = self._row(cash_rows, ["Cash from Operating Activity +", "Cash from Operating Activity"], cash_index)
        free_cashflow_cr = self._row(cash_rows, ["Free Cash Flow"], cash_index)
        capital_expenditure_cr = self._row(cash_rows, ["Capital Expenditure", "Capital Expenditure +"], cash_index)
        if capital_expenditure_cr is None and operating_cashflow_cr is not None and free_cashflow_cr is not None:
            capital_expenditure_cr = operating_cashflow_cr - free_cashflow_cr

        market_cap = self._cr(market_cap_cr)
        debt = self._cr(debt_cr)
        equity = self._cr(equity_cr)
        shares = market_cap / price if market_cap is not None and price not in (None, 0) else None
        pb = price / book_value if price is not None and book_value not in (None, 0) else None
        debt_equity = debt_cr / equity_cr if debt_cr is not None and equity_cr not in (None, 0) else None
        roa = latest_profit / assets_cr if latest_profit is not None and assets_cr not in (None, 0) else None
        current_ratio = current_assets_cr / current_liabilities_cr if current_assets_cr is not None and current_liabilities_cr not in (None, 0) else None

        pe = ratios.get("Stock P/E")
        peg = pe / (eps_cagr_3y * 100) if pe is not None and eps_cagr_3y is not None and eps_cagr_3y > 0 else None

        annual_ebitda = None if is_financial else ((latest_op or 0) + (latest_dep or 0) if latest_op is not None or latest_dep is not None else None)
        ttm_ebitda = None if is_financial else ((ttm_op or 0) + (ttm_dep or 0) if ttm_op is not None or ttm_dep is not None else None)
        enterprise_value = None if is_financial or market_cap is None or debt is None else market_cap + debt
        ev_ebitda = enterprise_value / self._cr(ttm_ebitda) if enterprise_value is not None and ttm_ebitda not in (None, 0) else None
        ev_revenue = enterprise_value / self._cr(ttm_sales) if enterprise_value is not None and ttm_sales not in (None, 0) else None

        financing_margin = self._row(pl_rows, ["Financing Margin %"], ttm if ttm is not None else latest)
        operating_margin = (
            self._pct(financing_margin)
            if is_financial and financing_margin is not None
            else self._pct(ttm_op / ttm_sales * 100) if ttm_op is not None and ttm_sales not in (None, 0) else None
        )
        profit_margin = self._pct(ttm_profit / ttm_sales * 100) if ttm_profit is not None and ttm_sales not in (None, 0) else None

        return {
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
            "trailingPE": pe,
            "priceToBook": pb,
            "pegRatio": peg,
            "priceToSalesTrailing12Months": market_cap_cr / ttm_sales if market_cap_cr is not None and ttm_sales not in (None, 0) else None,
            "enterpriseToEbitda": ev_ebitda,
            "enterpriseToRevenue": ev_revenue,
            "dividendYield": self._pct(ratios.get("Dividend Yield")),
            "returnOnEquity": self._pct(ratios.get("ROE")),
            "returnOnAssets": roa,
            "returnOnCapitalEmployed": self._pct(ratios.get("ROCE")),
            "debtToEquity": debt_equity,
            "currentRatio": current_ratio,
            "sector": sector,
            "industry": None,
            "_source": "Screener.in",
            "totalRevenue": self._cr(ttm_sales),
            "operatingProfit": self._cr(ttm_op),
            "netIncomeToCommon": self._cr(ttm_profit),
            "trailingEps": ttm_eps,
            "ebitda": self._cr(ttm_ebitda),
            "operatingCashflow": self._cr(operating_cashflow_cr),
            "freeCashflow": self._cr(free_cashflow_cr),
            "capitalExpenditure": self._cr(capital_expenditure_cr),
            "totalCash": None,
            "totalDebt": debt,
            "totalAssets": self._cr(assets_cr),
            "totalLiabilities": self._cr(liabilities_cr),
            "operatingMargins": operating_margin,
            "profitMargins": profit_margin,
            "payoutRatio": self._pct(latest_payout),
            "revenueGrowth": self._pct(growth.get("Compounded Sales Growth", {}).get("TTM")),
            "earningsGrowth": self._pct(growth.get("Compounded Profit Growth", {}).get("TTM")),
            "earningsQuarterlyGrowth": None,
        }

    def financial_history(self, symbol: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
        soup, extracted = self._extract(symbol)
        growth = extracted["growth"]
        sector = self._sector_for_symbol(symbol)
        is_financial = self._is_financial_company(sector)

        income_headers, income = self._table(soup, "profit-loss")
        balance_headers, balance = self._table(soup, "balance-sheet")
        cash_headers, cash = self._table(soup, "cash-flow")

        def value(rows: dict[str, list[float | None]], labels: list[str], index: int) -> float | None:
            return self._row(rows, labels, index)

        revenue_labels = ["Revenue", "Revenue +", "Sales", "Sales +"]
        operating_labels = ["Operating Profit", "Financing Profit"]
        profit_labels = ["Net Profit", "Net Profit +", "Profit after tax"]

        income_rows: list[dict[str, Any]] = []
        for index in self._annual_indices(income_headers):
            period = income_headers[index]
            sales = value(income, revenue_labels, index)
            op = value(income, operating_labels, index)
            dep = value(income, ["Depreciation"], index)
            profit = value(income, profit_labels, index)
            eps = value(income, ["EPS in Rs"], index)
            row: dict[str, Any] = {"asOfDate": f"{period[-4:]}-03-31", "periodType": "12M"}
            if sales is not None: row["annualTotalRevenue"] = {"raw": self._cr(sales)}
            if op is not None: row["annualOperatingIncome"] = {"raw": self._cr(op)}
            if dep is not None and op is not None and not is_financial: row["annualEBITDA"] = {"raw": self._cr(op + dep)}
            if profit is not None: row["annualNetIncome"] = {"raw": self._cr(profit)}
            if eps is not None: row["annualDilutedEPS"] = {"raw": eps}
            income_rows.append(row)

        balance_rows: list[dict[str, Any]] = []
        for index in self._annual_indices(balance_headers):
            period = balance_headers[index]
            equity_capital = value(balance, ["Equity Capital"], index)
            reserves = value(balance, ["Reserves"], index)
            debt = value(balance, ["Borrowings", "Borrowings +", "Borrowing"], index)
            assets = value(balance, ["Total Assets"], index)
            liabilities = value(balance, ["Total Liabilities"], index)
            row: dict[str, Any] = {"asOfDate": f"{period[-4:]}-03-31", "periodType": "12M"}
            if equity_capital is not None or reserves is not None: row["annualStockholdersEquity"] = {"raw": self._cr((equity_capital or 0) + (reserves or 0))}
            if debt is not None: row["annualTotalDebt"] = {"raw": self._cr(debt)}
            if assets is not None: row["annualTotalAssets"] = {"raw": self._cr(assets)}
            if liabilities is not None: row["annualTotalLiabilitiesNetMinorityInterest"] = {"raw": self._cr(liabilities)}
            balance_rows.append(row)

        cash_rows: list[dict[str, Any]] = []
        for index in self._annual_indices(cash_headers):
            period = cash_headers[index]
            cfo = value(cash, ["Cash from Operating Activity +", "Cash from Operating Activity"], index)
            fcf = value(cash, ["Free Cash Flow"], index)
            capex = value(cash, ["Capital Expenditure", "Capital Expenditure +"], index)
            if capex is None and cfo is not None and fcf is not None: capex = cfo - fcf
            row: dict[str, Any] = {"asOfDate": f"{period[-4:]}-03-31", "periodType": "12M"}
            if cfo is not None: row["annualOperatingCashFlow"] = {"raw": self._cr(cfo)}
            if fcf is not None: row["annualFreeCashFlow"] = {"raw": self._cr(fcf)}
            if capex is not None: row["annualCapitalExpenditure"] = {"raw": self._cr(capex)}
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
                "annualCapitalExpenditure": cash_rows,
                "annualFreeCashFlow": cash_rows,
            },
            "growth": growth,
        }
