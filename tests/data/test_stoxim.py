import pytest

from backend.services.data.stoxim import StoximClient
from backend.config.settings import Settings


@pytest.fixture
def client():
    return StoximClient(settings=Settings(stoxim_api_key="test-key"))


def test_fetch_fundamentals_not_implemented(client):
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(client.fetch_fundamentals("RELIANCE"))


def test_search_symbols_not_implemented(client):
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(client.search_symbols("RELIANCE"))
