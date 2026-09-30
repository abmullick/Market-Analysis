from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.config.settings import Settings

try:
    from curl_cffi import requests as curl_requests
except ImportError:  # pragma: no cover
    curl_requests = None


class YahooFinanceError(RuntimeError):
    pass


class YahooFinanceClient:
    """Server-side Yahoo Finance client using browser-like TLS when available."""

    hosts = ("https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }

    def __init__(self, settings: Settings):
        self.timeout = (10, 45)

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for host in self.hosts:
            try:
                if curl_requests is not None:
                    response = curl_requests.get(
                        host + path,
                        params=params,
                        headers=self.headers,
                        impersonate="chrome",
                        timeout=self.timeout,
                    )
                else:
                    import requests
                    response = requests.get(host + path, params=params, headers=self.headers, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise YahooFinanceError("Yahoo returned an invalid response")
                return payload
            except Exception as exc:
                last_error = exc
        raise YahooFinanceError(f"Yahoo Finance request failed: {last_error}") from last_error

    @staticmethod
    def _unwrap(value: Any) -> Any:
        if isinstance(value, dict) and "raw" in value:
            return value["raw"]
        return value

    def quote_summary(self, symbol: str) -> dict[str, Any]:
        modules = ",".join([
            "price", "summaryDetail", "defaultKeyStatistics", "financialData",
            "assetProfile", "quoteType"
        ])
        payload = self._get(
            f"/v10/finance/quoteSummary/{symbol.upper()}",
            {"modules": modules},
        )
        results = payload.get("quoteSummary", {}).get("result") or []
        if not results:
            raise YahooFinanceError(f"No Yahoo Finance data found for {symbol}")
        merged: dict[str, Any] = {}
        for module in results:
            if isinstance(module, dict):
                merged.update(module)
        return merged

    def fundamentals_timeseries(self, symbol: str, types: list[str], years: int = 6) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start = now.replace(year=now.year - years)
        payload = self._get(
            f"/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol.upper()}",
            {
                "symbol": symbol.upper(),
                "type": ",".join(types),
                "period1": int(start.timestamp()),
                "period2": int(now.timestamp()),
                "merge": "true",
            },
        )
        return payload.get("timeseries", {})
