from typing import Any

import httpx

from backend.config.settings import Settings
from backend.utils.logging import logger


class AmfiClient:
    def __init__(self, settings: Settings):
        self.nav_url = settings.amfi_nav_url

    async def fetch_nav_all(self) -> str:
        logger.info("Fetching AMFI NAVAll.txt")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(self.nav_url, timeout=30.0)
            response.raise_for_status()
            return response.text
