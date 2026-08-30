import sys
from pathlib import Path

# scripts/update_data.py
# Orchestrates data fetching from providers into data/raw/ and data/cache/.
# This is a placeholder. Replace with actual provider calls when ready.

sys.path.insert(0, str(Path(__file__).parent))

from backend.services.data.stoxim import StoximClient
from backend.config.settings import Settings


def update():
    settings = Settings()
    client = StoximClient(settings=settings)
    raise NotImplementedError("Data update pipeline not yet implemented.")


if __name__ == "__main__":
    update()
