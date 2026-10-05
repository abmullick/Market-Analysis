from typing import Any

import httpx

from backend.config.settings import Settings
from backend.utils.logging import logger


class AmfiClient:
    def __init__(self, settings: Settings):
        self.nav_url = settings.amfi_nav_url

    async def fetch_nav_all(self) -> str:
        import time

        started = time.perf_counter()
        logger.info("TIMING: AMFI fetch START")

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(self.nav_url, timeout=30.0)
            response.raise_for_status()
            text = response.text

        elapsed = time.perf_counter() - started
        logger.info(
            "TIMING: AMFI fetch END | %.3f sec | HTTP %s | %d bytes",
            elapsed,
            response.status_code,
            len(text),
        )

        return text
