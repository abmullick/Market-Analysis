import sys
import subprocess
from pathlib import Path


def update_data():
    script = Path(__file__).parent / "update_data.py"
    subprocess.run([sys.executable, str(script)], check=True)


def calculate_rankings():
    script = Path(__file__).parent / "calculate_rankings.py"
    subprocess.run([sys.executable, str(script)], check=True)


if __name__ == "__main__":
    update_data()
    calculate_rankings()
