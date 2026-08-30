import pytest

from backend.services.portfolio.analysis import PortfolioAnalyzer
from backend.models.portfolio import Holding


@pytest.fixture
def analyzer():
    return PortfolioAnalyzer()


def test_analyze_holdings_not_implemented(analyzer):
    with pytest.raises(NotImplementedError):
        analyzer.analyze_holdings([Holding(symbol="RELIANCE")])


def test_analyze_portfolio_not_implemented(analyzer):
    with pytest.raises(NotImplementedError):
        analyzer.analyze_portfolio([Holding(symbol="RELIANCE")])
