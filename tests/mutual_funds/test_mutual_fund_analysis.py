import pytest

from backend.services.mutual_funds.analysis import MutualFundAnalyzer


@pytest.fixture
def analyzer():
    return MutualFundAnalyzer()


def test_analyze_fund_not_implemented(analyzer):
    with pytest.raises(NotImplementedError):
        analyzer.analyze_fund({})
