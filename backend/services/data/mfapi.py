import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx

from backend.config.settings import Settings
from backend.utils.logging import logger


class MfapiError(Exception):
    """Raised when MFAPI requests fail."""
    pass


class MfapiClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.mfapi_base_url.rstrip("/")

    async def fetch_scheme(self, scheme_code: str) -> dict[str, Any]:
        url = f"{self.base_url}/mf/{scheme_code}"
        logger.info("Fetching MF scheme: %s", scheme_code)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0)
            response.raise_for_status()
            return response.json()

    async def fetch_nav_history(
        self,
        scheme_code: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/mf/{scheme_code}"
        params = {}
        if start_date:
            params["startDate"] = start_date.strftime("%d-%m-%Y")
        if end_date:
            params["endDate"] = end_date.strftime("%d-%m-%Y")

        param_str = f" start={params.get('startDate')} end={params.get('endDate')}" if params else ""
        logger.info("Fetching MF NAV history: %s%s", scheme_code, param_str)

        max_retries = 2
        overall_timeout = 45.0

        async def _fetch_with_retries():
            for attempt in range(max_retries + 1):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, params=params, timeout=20.0)
                        response.raise_for_status()
                        data = response.json()
                        if isinstance(data, dict) and "error" in data:
                            raise MfapiError(f"MFAPI error for scheme {scheme_code}: {data['error']}")
                        if not isinstance(data, dict) or "data" not in data:
                            raise MfapiError(f"Unexpected MFAPI response for scheme {scheme_code}: missing 'data' field")
                        return data
                except MfapiError:
                    raise
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning("MFAPI attempt %d failed for %s: %s — retrying", attempt + 1, scheme_code, e)
                        await asyncio.sleep(1.0 * (attempt + 1))
                    else:
                        raise MfapiError(
                            f"MFAPI request failed for scheme {scheme_code} after {max_retries + 1} attempts: {e}"
                        ) from e

        try:
            return await asyncio.wait_for(_fetch_with_retries(), timeout=overall_timeout)
        except asyncio.TimeoutError:
            raise MfapiError(f"MFAPI request timed out for scheme {scheme_code} after {overall_timeout}s")

    async def search_schemes(self, query: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/mf/search"
        params = {"query": query}
        logger.info("Searching MF schemes: %s", query)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            return data.get("schemes", [])
