from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import curl_cffi.requests

from backend.config.settings import Settings


class YahooFinanceError(Exception):
    """Yahoo Finance API error."""


def number(value: Any) -> Optional[float]:
    """Convert Yahoo numeric values to float."""

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        if "raw" in value:
            return number(value["raw"])

        if "fmt" in value:
            return number(value["fmt"])

        return None

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        # Remove common formatting.
        value = value.replace(",", "")

        try:
            return float(value)
        except ValueError:
            return None

    return None


def raw_value(value: Any) -> Optional[float]:
    """Extract Yahoo's raw numeric value."""

    if isinstance(value, dict):
        return number(value.get("raw"))

    return number(value)


class YahooFinanceClient:
    """
    Lightweight Yahoo Finance client.

    Uses Yahoo's public/anonymous endpoints through curl_cffi.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        self.session = curl_cffi.requests.Session(
            impersonate="chrome",
        )

        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/154.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

        self.crumb: Optional[str] = None

        self._authenticate()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        """
        Establish Yahoo's anonymous session cookie and obtain the
        cookie-bound crumb.

        fc.yahoo.com commonly returns HTTP 404. That response can
        nevertheless establish the Yahoo cookies, so it is deliberately
        not treated as an authentication failure.
        """

        try:
            self.session.get(
                "https://fc.yahoo.com",
                timeout=15,
                allow_redirects=True,
            )

            response = self.session.get(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                timeout=15,
                allow_redirects=True,
            )

            response.raise_for_status()

            crumb = response.text.strip()

            if (
                not crumb
                or crumb.startswith("<")
                or "Too Many Requests" in crumb
            ):
                raise YahooFinanceError(
                    f"Yahoo returned an invalid crumb: {crumb[:100]}"
                )

            self.crumb = crumb

        except YahooFinanceError:
            raise

        except Exception as exc:
            raise YahooFinanceError(
                f"Yahoo Finance authentication failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _get(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
    ):
        """GET request with Yahoo crumb attached."""

        params = dict(params or {})

        if self.crumb:
            params["crumb"] = self.crumb

        response = self.session.get(
            url,
            params=params,
            timeout=30,
            allow_redirects=True,
        )

        response.raise_for_status()

        return response

    def _get_json(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:

        url = (
            "https://query1.finance.yahoo.com"
            + path
        )

        try:
            response = self._get(
                url,
                params,
            )

            return response.json()

        except Exception as exc:
            raise YahooFinanceError(
                f"Yahoo Finance request failed: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Quote summary
    # ------------------------------------------------------------------

    def quote_summary(
        self,
        symbol: str,
    ) -> dict[str, Any]:

        symbol = symbol.strip().upper()

        modules = ",".join(
            [
                "price",
                "summaryDetail",
                "defaultKeyStatistics",
                "financialData",
                "summaryProfile",
            ]
        )

        payload = self._get_json(
            f"/v10/finance/quoteSummary/{symbol}",
            {
                "modules": modules,
            },
        )

        quote_summary = (
            payload
            .get("quoteSummary", {})
        )

        result = (
            quote_summary
            .get("result")
            or []
        )

        if not result:
            error = (
                quote_summary
                .get("error")
            )

            raise YahooFinanceError(
                f"No quote-summary data returned for {symbol}: "
                f"{error}"
            )

        data: dict[str, Any] = {}

        for module in result[0].values():
            if not isinstance(module, dict):
                continue

            for key, value in module.items():
                if key == "maxAge":
                    continue

                data[key] = raw_value(value)

                # Some fields are strings rather than raw values.
                if data[key] is None and isinstance(
                    value,
                    str,
                ):
                    data[key] = value

        # Identity/profile fields.
        result_item = result[0]

        price_module = result_item.get("price", {})

        profile_module = result_item.get(
            "summaryProfile",
            {},
        )

        financial_module = result_item.get(
            "financialData",
            {},
        )

        summary_module = result_item.get(
            "summaryDetail",
            {},
        )

        statistics_module = result_item.get(
            "defaultKeyStatistics",
            {},
        )

        data.update(
            {
                "longName": (
                    price_module.get("longName")
                    or price_module.get("shortName")
                ),
                "shortName": price_module.get(
                    "shortName"
                ),
                "exchangeName": price_module.get(
                    "exchangeName"
                ),
                "fullExchangeName": price_module.get(
                    "fullExchangeName"
                ),
                "currency": price_module.get(
                    "currency"
                ),
                "sector": profile_module.get(
                    "sector"
                ),
                "industry": profile_module.get(
                    "industry"
                ),
                "country": profile_module.get(
                    "country"
                ),
            }
        )

        # Explicitly normalize commonly used fields.
        modules_data = {
            **price_module,
            **summary_module,
            **statistics_module,
            **financial_module,
        }

        for key, value in modules_data.items():
            normalized = raw_value(value)

            if normalized is not None:
                data[key] = normalized

        return data

    # ------------------------------------------------------------------
    # Fundamentals timeseries
    # ------------------------------------------------------------------

    def fundamentals_timeseries(
        self,
        symbol: str,
        types: list[str],
        years: int = 6,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Fetch annual fundamentals from Yahoo's fundamentals-timeseries
        endpoint.

        Yahoo returns:

            timeseries.result[]

        Each metric contains records like:

            {
                "asOfDate": "2026-03-31",
                "periodType": "12M",
                "currencyCode": "INR",
                "reportedValue": {
                    "raw": 123456,
                    "fmt": "123.46B"
                }
            }
        """

        symbol = symbol.strip().upper()

        now = datetime.now(timezone.utc)

        start = now - timedelta(
            days=365 * years
        )

        period1 = int(
            start.timestamp()
        )

        period2 = int(
            now.timestamp()
        )

        params = {
            "symbol": symbol,
            "type": ",".join(types),
            "period1": period1,
            "period2": period2,
            "merge": "false",
            "padTimeSeries": "false",
            "lang": "en-US",
            "region": "US",
        }

        payload = self._get_json(
            f"/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}",
            params,
        )

        timeseries = payload.get(
            "timeseries",
            {},
        )

        result = (
            timeseries.get("result")
            or []
        )

        output: dict[
            str,
            list[dict[str, Any]]
        ] = {}

        for item in result:
            if not isinstance(item, dict):
                continue

            for key, value in item.items():
                if key in {
                    "meta",
                    "timestamp",
                }:
                    continue

                if isinstance(value, list):
                    output[key] = value

        return output

    # ------------------------------------------------------------------
    # Financial history
    # ------------------------------------------------------------------

    def financial_history(
        self,
        symbol: str,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:

        income_types = [
            "annualTotalRevenue",
            "annualGrossProfit",
            "annualOperatingIncome",
            "annualEBITDA",
            "annualNetIncome",
            "annualDilutedEPS",
            "annualOperatingCashFlow",
        ]

        balance_types = [
            "annualTotalAssets",
            "annualTotalLiabilitiesNetMinorityInterest",
            "annualStockholdersEquity",
            "annualCashCashEquivalentsAndShortTermInvestments",
            "annualTotalDebt",
            "annualCurrentAssets",
            "annualCurrentLiabilities",
        ]

        cash_types = [
            "annualOperatingCashFlow",
            "annualCapitalExpenditure",
            "annualFreeCashFlow",
        ]

        income = self.fundamentals_timeseries(
            symbol,
            income_types,
        )

        balance = self.fundamentals_timeseries(
            symbol,
            balance_types,
        )

        cash = self.fundamentals_timeseries(
            symbol,
            cash_types,
        )

        return {
            "income": income,
            "balance": balance,
            "cash": cash,
        }