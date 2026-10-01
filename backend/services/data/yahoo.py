from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import curl_cffi.requests

from backend.config.settings import Settings
from backend.services.data.screener import ScreenerFinanceClient, ScreenerFinanceError


class YahooFinanceError(Exception):
    """Yahoo Finance API error."""


def number(value: Any) -> Optional[float]:
    """Convert Yahoo numeric values to float."""
    if value is None or isinstance(value, bool):
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
        value = value.strip().replace(",", "")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
    return None


def raw_value(value: Any) -> Optional[float]:
    if isinstance(value, dict):
        return number(value.get("raw"))
    return number(value)


class YahooFinanceClient:
    """Yahoo client with an Indian-equity Screener.in fallback.

    Yahoo's cookie/crumb endpoint is routinely HTTP 429 from cloud/datacenter
    IPs such as Render. NSE-listed fundamentals therefore use Screener.in
    directly, while Yahoo remains available for non-NSE symbols and as a
    fallback. Authentication is lazy so a Yahoo 429 can never prevent the
    FastAPI application from starting.
    """

    QUERY_HOSTS = (
        "https://query2.finance.yahoo.com",
        "https://query1.finance.yahoo.com",
    )
    COOKIE_URL = "https://fc.yahoo.com"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
    MAX_RETRIES = 2
    RETRY_DELAYS = (1.5, 3.0, 6.0)

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = curl_cffi.requests.Session(impersonate="chrome")
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        })
        self.crumb: Optional[str] = None
        self._active_host = self.QUERY_HOSTS[0]
        self._auth_error: Optional[Exception] = None
        self._screener = ScreenerFinanceClient()

    @staticmethod
    def _is_nse_symbol(symbol: str) -> bool:
        return symbol.strip().upper().endswith(".NS")

    def _authenticate(self) -> None:
        """Establish a Yahoo cookie and cookie-bound crumb lazily."""
        errors: list[str] = []

        try:
            self.session.get(
                self.COOKIE_URL,
                timeout=10,
                allow_redirects=True,
            )
        except Exception:
            pass

        for host in self.QUERY_HOSTS:
            url = f"{host}/v1/test/getcrumb"
            try:
                response = self._request(
                    url,
                    params=None,
                    include_crumb=False,
                )
                crumb = response.text.strip()
                if not crumb or crumb.startswith("<") or "Too Many Requests" in crumb:
                    raise YahooFinanceError(
                        f"Yahoo returned an invalid crumb: {crumb[:100]}"
                    )
                self.crumb = crumb
                self._active_host = host
                self._auth_error = None
                return
            except Exception as exc:
                errors.append(f"{host}: {exc}")

        self._auth_error = YahooFinanceError(
            "Yahoo Finance authentication failed after trying both Yahoo API hosts: "
            + " | ".join(errors)
        )
        raise self._auth_error

    def _ensure_auth(self) -> None:
        if self.crumb:
            return
        if self._auth_error is not None:
            raise self._auth_error
        self._authenticate()

    def _request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        include_crumb: bool = True,
    ):
        params = dict(params or {})
        if include_crumb and self.crumb:
            params["crumb"] = self.crumb

        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=30,
                    allow_redirects=True,
                )
                if response.status_code != 429:
                    response.raise_for_status()
                    return response

                retry_after = response.headers.get("Retry-After")
                delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                last_error = YahooFinanceError(
                    f"Yahoo HTTP 429 Too Many Requests from {url}"
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(delay)
            except Exception as exc:
                last_error = exc
                if attempt < self.MAX_RETRIES:
                    time.sleep(
                        self.RETRY_DELAYS[
                            min(attempt, len(self.RETRY_DELAYS) - 1)
                        ]
                    )

        raise last_error or YahooFinanceError("Yahoo request failed")

    def _get_json(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        self._ensure_auth()
        hosts = [
            self._active_host,
            *[h for h in self.QUERY_HOSTS if h != self._active_host],
        ]
        errors: list[str] = []

        for host in hosts:
            try:
                response = self._request(
                    host + path,
                    params=params,
                    include_crumb=True,
                )
                return response.json()
            except Exception as exc:
                errors.append(f"{host}: {exc}")

        raise YahooFinanceError(
            "Yahoo Finance request failed on all API hosts: "
            + " | ".join(errors)
        )

    def _screener_quote_summary(self, symbol: str) -> dict[str, Any]:
        try:
            return self._screener.quote_summary(symbol)
        except ScreenerFinanceError as exc:
            raise YahooFinanceError(
                f"Screener.in fundamentals fallback failed for {symbol}: {exc}"
            ) from exc

    def _screener_history(self, symbol: str) -> dict[str, dict[str, list[dict[str, Any]]]]:
        try:
            return self._screener.financial_history(symbol)
        except ScreenerFinanceError as exc:
            raise YahooFinanceError(
                f"Screener.in financial-history fallback failed for {symbol}: {exc}"
            ) from exc

    def quote_summary(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.strip().upper()

        # For NSE-listed stocks, use the Indian fundamentals source first.
        # This avoids Yahoo's Render/datacenter crumb throttling entirely.
        if self._is_nse_symbol(symbol):
            try:
                return self._screener_quote_summary(symbol)
            except YahooFinanceError:
                pass

        try:
            modules = ",".join([
                "price",
                "summaryDetail",
                "defaultKeyStatistics",
                "financialData",
                "summaryProfile",
            ])
            payload = self._get_json(
                f"/v10/finance/quoteSummary/{symbol}",
                {"modules": modules},
            )
        except YahooFinanceError:
            if self._is_nse_symbol(symbol):
                return self._screener_quote_summary(symbol)
            raise

        quote_summary = payload.get("quoteSummary", {})
        result = quote_summary.get("result") or []
        if not result:
            raise YahooFinanceError(
                f"No quote-summary data returned for {symbol}: "
                f"{quote_summary.get('error')}"
            )

        result_item = result[0]
        data: dict[str, Any] = {}

        for module in result_item.values():
            if not isinstance(module, dict):
                continue
            for key, value in module.items():
                if key == "maxAge":
                    continue
                data[key] = raw_value(value)
                if data[key] is None and isinstance(value, str):
                    data[key] = value

        price_module = result_item.get("price", {})
        profile_module = result_item.get("summaryProfile", {})
        data.update({
            "longName": price_module.get("longName") or price_module.get("shortName"),
            "shortName": price_module.get("shortName"),
            "exchangeName": price_module.get("exchangeName"),
            "fullExchangeName": price_module.get("fullExchangeName"),
            "currency": price_module.get("currency"),
            "sector": profile_module.get("sector"),
            "industry": profile_module.get("industry"),
            "country": profile_module.get("country"),
            "_source": "Yahoo Finance",
        })

        for module_name in (
            "price",
            "summaryDetail",
            "defaultKeyStatistics",
            "financialData",
        ):
            for key, value in result_item.get(module_name, {}).items():
                normalized = raw_value(value)
                if normalized is not None:
                    data[key] = normalized

        return data

    def fundamentals_timeseries(
        self,
        symbol: str,
        types: list[str],
        years: int = 6,
    ) -> dict[str, list[dict[str, Any]]]:
        symbol = symbol.strip().upper()
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=365 * years)
        params = {
            "symbol": symbol,
            "type": ",".join(types),
            "period1": int(start.timestamp()),
            "period2": int(now.timestamp()),
            "merge": "false",
            "padTimeSeries": "false",
            "lang": "en-US",
            "region": "US",
        }
        payload = self._get_json(
            f"/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}",
            params,
        )
        result = payload.get("timeseries", {}).get("result") or []
        output: dict[str, list[dict[str, Any]]] = {}
        for item in result:
            if not isinstance(item, dict):
                continue
            for key, value in item.items():
                if key not in {"meta", "timestamp"} and isinstance(value, list):
                    output[key] = value
        return output

    def financial_history(
        self,
        symbol: str,
    ) -> dict[str, dict[str, list[dict[str, Any]]]]:
        symbol = symbol.strip().upper()

        if self._is_nse_symbol(symbol):
            try:
                return self._screener_history(symbol)
            except YahooFinanceError:
                pass

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

        try:
            return {
                "income": self.fundamentals_timeseries(symbol, income_types),
                "balance": self.fundamentals_timeseries(symbol, balance_types),
                "cash": self.fundamentals_timeseries(symbol, cash_types),
            }
        except YahooFinanceError:
            if self._is_nse_symbol(symbol):
                return self._screener_history(symbol)
            raise
