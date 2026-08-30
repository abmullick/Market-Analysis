import pytest

from backend.services.stocks.screener import ScreenerEngine


@pytest.fixture
def engine():
    return ScreenerEngine()


def test_score_growth_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.score_growth(None)


def test_score_roe_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.score_roe(None)


def test_score_value_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.score_value(None)


def test_score_quality_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.score_quality(None)


def test_score_overall_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.score_overall(None)


def test_apply_strategy_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        engine.apply_strategy([], "growth")
