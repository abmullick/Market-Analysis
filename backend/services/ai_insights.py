from typing import Any

from backend.config.settings import Settings
from backend.utils.logging import logger


class AIInsightService:
    def __init__(self, settings: Settings):
        self.api_key = settings.groq_api_key
        self.model = "llama-3.1-8b-instant"  # placeholder model

    async def generate_insights(self, metrics: dict[str, Any]) -> str:
        raise NotImplementedError("AI insights integration not yet implemented.")
