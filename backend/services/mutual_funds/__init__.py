from backend.services.mutual_funds.calculator import MetricsCalculator
from backend.services.mutual_funds.fetcher import MutualFundFetcher
from backend.services.mutual_funds.insight_payload import build_mutual_fund_insight_context
from backend.services.mutual_funds.normalizer import (
    normalize_nav_history,
    normalize_scheme,
    normalize_search_result,
)
from backend.services.mutual_funds.ranking import RankingEngine

# Install the optimized portfolio-builder fund search after MutualFundFetcher
# has been imported. This preserves the existing public API while replacing
# only the expensive per-keystroke search implementation.
from backend.services.mutual_funds.search_index import install_search_optimization
install_search_optimization()
