import logging
import sys

logger = logging.getLogger("market_analysis")
logger.setLevel(logging.DEBUG if __name__ == "__main__" else logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
