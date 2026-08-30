from typing import Any

from backend.models.portfolio import Holding


class PortfolioAnalyzer:
    def analyze_holdings(self, holdings: list[Holding]) -> list[dict[str, Any]]:
        raise NotImplementedError("Holding analysis not yet implemented.")

    def analyze_portfolio(self, holdings: list[Holding]) -> dict[str, Any]:
        raise NotImplementedError("Portfolio analysis not yet implemented.")
