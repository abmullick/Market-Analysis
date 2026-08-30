import pytest

from backend.services.ai.groq import AIInsightService
from backend.config.settings import Settings


@pytest.fixture
def service():
    return AIInsightService(settings=Settings(groq_api_key="test-key"))


def test_generate_insights_not_implemented(service):
    with pytest.raises(NotImplementedError):
        import asyncio
        asyncio.run(service.generate_insights({}))
