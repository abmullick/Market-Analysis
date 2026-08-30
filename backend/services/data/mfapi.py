from typing import Any

import httpx

from backend.config.settings import Settings
from backend.utils.logging import logger


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

    async def fetch_nav_history(self, scheme_code: str) -> dict[str, Any]:
        url = f"{self.base_url}/mf/{scheme_code}"
        logger.info("Fetching MF NAV history: %s", scheme_code)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "error" in data:
                raise ValueError(f"MFAPI error for scheme {scheme_code}: {data['error']}")
            if not isinstance(data, dict) or "data" not in data:
                raise ValueError(f"Unexpected MFAPI response for scheme {scheme_code}: missing 'data' field")
            return data

    async def search_schemes(self, query: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/mf/search"
        params = {"query": query}
        logger.info("Searching MF schemes: %s", query)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            return data.get("schemes", [])
