import pytest

from backend.services.portfolio.parser import PortfolioParser


@pytest.fixture
def parser():
    return PortfolioParser()


def test_parse_not_implemented(parser):
    with pytest.raises(NotImplementedError):
        parser.parse({})
