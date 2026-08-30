from typing import Any

from backend.models.portfolio import Holding


class PortfolioParser:
    def parse(self, raw: Any) -> list[Holding]:
        raise NotImplementedError("Portfolio parsing not yet implemented.")
