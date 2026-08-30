from typing import Any

from backend.config.settings import Settings
from backend.utils.logging import logger


class StoximClient:
    def __init__(self, settings: Settings):
        self.api_key = settings.stoxim_api_key
        self.base_url = "https://api.stoxim.in"  # placeholder base URL

    async def fetch_fundamentals(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError("Stoxim API integration not yet implemented.")

    async def search_symbols(self, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError("Stoxim API integration not yet implemented.")
