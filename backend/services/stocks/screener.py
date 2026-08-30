from typing import Any

from backend.models.fundamentals import Fundamentals


class ScreenerEngine:
    def score_growth(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Growth scoring not yet implemented.")

    def score_roe(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("ROE scoring not yet implemented.")

    def score_value(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Value scoring not yet implemented.")

    def score_quality(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Quality scoring not yet implemented.")

    def score_overall(self, fundamentals: Fundamentals) -> float:
        raise NotImplementedError("Overall scoring not yet implemented.")

    def apply_strategy(self, fundamentals: list[Fundamentals], strategy: str) -> list[dict[str, Any]]:
        raise NotImplementedError("Strategy application not yet implemented.")
