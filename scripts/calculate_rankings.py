import sys
from pathlib import Path

# scripts/calculate_rankings.py
# Reads cached fundamentals and writes rankings to data/rankings/.
# This is a placeholder. Replace with actual scoring logic when ready.

sys.path.insert(0, str(Path(__file__).parent))

from backend.services.stocks.screener import ScreenerEngine


def calculate():
    engine = ScreenerEngine()
    raise NotImplementedError("Ranking calculation not yet implemented.")


if __name__ == "__main__":
    calculate()
