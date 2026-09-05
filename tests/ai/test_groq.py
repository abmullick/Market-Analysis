import json
import os
from unittest.mock import patch, MagicMock

import pytest
from groq import RateLimitError, APIStatusError, APIConnectionError, BadRequestError
from google import genai

from backend.services.ai.groq import (
    AIInsightService,
    InsightRequest,
    InsightResponse,
    _extract_json_from_text,
    _repair_insight_response,
    _get_provider_config,
    _call_groq,
    _call_gemini,
    _build_prompt,
)
from backend.config.settings import Settings


def _mock_groq_response():
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "summary": "The fund shows strong 3-year performance with moderate volatility.",
        "key_points": [
            "3-year CAGR outperforms category median.",
            "Sharpe ratio indicates good risk-adjusted returns."
        ],
        "risks": [
            "Higher-than-average expense ratio could erode returns over time."
        ],
        "opportunities": [
            "Consistent outperformance in both bull and bear markets."
        ],
        "recommendation": "Consider for long-term equity allocation."
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def _mock_gemini_response():
    return MagicMock(
        text=json.dumps({
            "summary": "The fund shows strong 3-year performance with moderate volatility.",
            "key_points": [
                "3-year CAGR outperforms category median.",
                "Sharpe ratio indicates good risk-adjusted returns."
            ],
            "risks": [
                "Higher-than-average expense ratio could erode returns over time."
            ],
            "opportunities": [
                "Consistent outperformance in both bull and bear markets."
            ],
            "recommendation": "Consider for long-term equity allocation."
        })
    )


class TestExtractJsonFromText:
    def test_plain_json_object(self):
        text = '{"summary": "test"}'
        result = _extract_json_from_text(text)
        assert result == {"summary": "test"}

    def test_json_with_code_fences(self):
        text = "```json\n{\"summary\": \"test\"}\n```"
        result = _extract_json_from_text(text)
        assert result == {"summary": "test"}

    def test_json_with_extra_text_before_and_after(self):
        text = "Here is the result: {\"summary\": \"test\"} Hope this helps!"
        result = _extract_json_from_text(text)
        assert result == {"summary": "test"}

    def test_malformed_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json_from_text("not valid json {{{")


class TestRepairInsightResponse:
    def test_complete_response_unchanged(self):
        parsed = {
            "summary": "test",
            "key_points": ["a"],
            "risks": ["b"],
            "opportunities": ["c"],
            "recommendation": "d"
        }
        result = _repair_insight_response(parsed)
        assert result == parsed

    def test_missing_fields_repaired(self):
        parsed = {"summary": "test"}
        result = _repair_insight_response(parsed)
        assert result["key_points"] == []
        assert result["risks"] == []
        assert result["opportunities"] == []
        assert result["recommendation"] is None

    def test_none_values_repaired(self):
        parsed = {"summary": "test", "key_points": None, "risks": None}
        result = _repair_insight_response(parsed)
        assert result["key_points"] == []
        assert result["risks"] == []

    def test_non_dict_returns_empty(self):
        assert _repair_insight_response("not a dict") == {}
        assert _repair_insight_response(None) == {}
        assert _repair_insight_response(123) == {}


class TestBuildPrompt:
    def test_prompt_contains_required_fields(self):
        request = InsightRequest(
            data={"fund_name": "Test Fund", "cagr": 15.0},
            context="fund_analysis",
            focus="performance"
        )
        prompt = _build_prompt(request)
        parsed = json.loads(prompt)
        assert parsed["data"] == {"fund_name": "Test Fund", "cagr": 15.0}
        assert parsed["context"] == "fund_analysis"
        assert parsed["focus"] == "performance"


class TestAIInsightService:
    @pytest.fixture
    def service(self):
        return AIInsightService(settings=Settings(groq_api_key="test-key"))

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_generate_insights_success(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.return_value = _mock_groq_response()

        data = {
            "fund_name": "HDFC Top 100",
            "category": "Large Cap",
            "three_year_cagr": 18.5,
            "five_year_cagr": 16.2,
            "sharpe_ratio": 1.2,
            "max_drawdown": -25.0
        }
        response = await service.generate_insights(data, context="fund_analysis")

        assert isinstance(response, InsightResponse)
        assert "strong 3-year performance" in response.summary
        assert len(response.key_points) == 2
        assert len(response.risks) == 1
        assert len(response.opportunities) == 1
        assert response.recommendation is not None

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_process_insight_request_success(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.return_value = _mock_groq_response()

        request = InsightRequest(
            data={"fund_name": "Test Fund", "cagr": 15.0},
            context="ranking_summary"
        )
        response = await AIInsightService.process_insight_request(request)

        assert isinstance(response, InsightResponse)
        assert response.summary
        assert isinstance(response.key_points, list)

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_malformed_groq_response_raises(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_message = MagicMock()
        mock_message.content = "not valid json {{{"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError):
            await service.generate_insights({"test": "data"})

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_api_failure_returns_safe_error(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.side_effect = Exception("Network error")

        with pytest.raises(RuntimeError) as ctx:
            await service.generate_insights({"test": "data"})
        assert "temporarily unavailable" in str(ctx.value).lower()

    @patch.dict(os.environ, {}, clear=True)
    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            request = InsightRequest(data={"test": "data"})
            with pytest.raises(ValueError) as ctx:
                await AIInsightService.process_insight_request(request)
            assert "GROQ_API_KEY" in str(ctx.value) or "GEMINI_API_KEY" in str(ctx.value)

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_validation_failure_raises(self, MockClient, service):
        mock_client = MockClient.return_value
        invalid_json = json.dumps({
            "summary": "Test",
            "key_points": "should be list",
            "risks": [],
            "opportunities": [],
        })
        mock_message = MagicMock()
        mock_message.content = invalid_json
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError):
            await service.generate_insights({"test": "data"})

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_transient_503_then_success(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.side_effect = [
            APIStatusError(
                message="high demand",
                response=MagicMock(status_code=503),
                body={"error": {"message": "high demand"}}
            ),
            _mock_groq_response(),
        ]

        response = await service.generate_insights({"test": "data"})
        assert isinstance(response, InsightResponse)
        assert mock_client.chat.completions.create.call_count == 2

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_all_retries_fail_returns_safe_error(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.side_effect = APIStatusError(
            message="high demand",
            response=MagicMock(status_code=503),
            body={"error": {"message": "high demand"}}
        )

        with pytest.raises(RuntimeError) as ctx:
            await service.generate_insights({"test": "data"})
        assert "temporarily unavailable" in str(ctx.value).lower()
        assert mock_client.chat.completions.create.call_count == 3

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_non_retryable_error_not_retried(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.side_effect = BadRequestError(
            message="bad request",
            response=MagicMock(status_code=400),
            body={"error": {"message": "bad request"}}
        )

        with pytest.raises(RuntimeError):
            await service.generate_insights({"test": "data"})
        assert mock_client.chat.completions.create.call_count == 1

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_quota_exhausted_429_not_retried(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.side_effect = RateLimitError(
            "Quota exceeded for groq",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Quota exceeded"}}
        )

        with pytest.raises(RuntimeError):
            await service.generate_insights({"test": "data"})
        assert mock_client.chat.completions.create.call_count == 1

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_transient_429_is_retried(self, MockClient, service):
        mock_client = MockClient.return_value
        transient_429 = RateLimitError(
            message="rate limit exceeded",
            response=MagicMock(status_code=429),
            body={"error": {"message": "rate limit exceeded"}}
        )
        mock_client.chat.completions.create.side_effect = [
            transient_429,
            _mock_groq_response(),
        ]

        response = await service.generate_insights({"test": "data"})
        assert isinstance(response, InsightResponse)
        assert mock_client.chat.completions.create.call_count == 2

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_exception_does_not_expose_internal_details(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.side_effect = APIStatusError(
            message="internal server error",
            response=MagicMock(status_code=500),
            body={"error": {"message": "internal server error"}}
        )

        with pytest.raises(RuntimeError) as ctx:
            await service.generate_insights({"test": "data"})
        body = str(ctx.value)
        assert "internal server error" not in body.lower()
        assert "stack" not in body.lower()
        assert "traceback" not in body.lower()

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_call_groq_uses_json_schema(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.return_value = _mock_groq_response()

        await service.generate_insights({"test": "data"})

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert "json_schema" in call_kwargs["response_format"]
        assert call_kwargs["response_format"]["json_schema"]["name"] == "InsightResponse"
        assert "schema" in call_kwargs["response_format"]["json_schema"]

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_empty_response_raises(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_message = MagicMock()
        mock_message.content = ""
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError):
            await service.generate_insights({"test": "data"})

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_json_with_code_fences(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_message = MagicMock()
        mock_message.content = "```json\n" + json.dumps({
            "summary": "Test",
            "key_points": ["a"],
            "risks": [],
            "opportunities": [],
        }) + "\n```"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        response = await service.generate_insights({"test": "data"})
        assert isinstance(response, InsightResponse)
        assert response.summary == "Test"

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_incomplete_response_repaired(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_message = MagicMock()
        mock_message.content = json.dumps({
            "summary": "Test",
            "key_points": ["a"],
            "risks": ["b"]
        })
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        response = await service.generate_insights({"test": "data"})
        assert isinstance(response, InsightResponse)
        assert response.opportunities == []
        assert response.recommendation is None

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_groq_413_tpm_not_retried(self, MockClient, service):
        mock_client = MockClient.return_value
        tpm_413 = APIStatusError(
            message="Request too large for model on tokens per minute (TPM): Limit 8000, Requested 8862",
            response=MagicMock(status_code=413),
            body={"error": {"message": "Request too large", "code": "rate_limit_exceeded"}}
        )
        mock_client.chat.completions.create.side_effect = tpm_413

        with pytest.raises(RuntimeError):
            await service.generate_insights({"test": "data"})
        assert mock_client.chat.completions.create.call_count == 1

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.0-flash"}, clear=True)
    @patch("backend.services.ai.groq.genai.Client")
    @pytest.mark.asyncio
    async def test_gemini_success(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.models.generate_content.return_value = _mock_gemini_response()

        request = InsightRequest(data={"test": "data"}, context="fund_analysis")
        response = await AIInsightService.process_insight_request(request)

        assert isinstance(response, InsightResponse)
        assert "strong 3-year performance" in response.summary
        assert len(response.risks) == 1
        assert len(response.opportunities) == 1

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-2.0-flash"}, clear=True)
    @patch("backend.services.ai.groq.genai.Client")
    @pytest.mark.asyncio
    async def test_gemini_api_failure_returns_safe_error(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.models.generate_content.side_effect = Exception("Network error")

        request = InsightRequest(data={"test": "data"}, context="fund_analysis")
        with pytest.raises(RuntimeError) as ctx:
            await AIInsightService.process_insight_request(request)
        assert "temporarily unavailable" in str(ctx.value).lower()

    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "openai/gpt-oss-120b"})
    @patch("backend.services.ai.groq.Groq")
    @pytest.mark.asyncio
    async def test_prompt_includes_context_and_focus(self, MockClient, service):
        mock_client = MockClient.return_value
        mock_client.chat.completions.create.return_value = _mock_groq_response()

        await service.generate_insights(
            {"fund_name": "Test"},
            context="ranking_summary",
            focus="consistency"
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        prompt = json.loads(call_kwargs["messages"][1]["content"])
        assert prompt["context"] == "ranking_summary"
        assert prompt["focus"] == "consistency"

    @pytest.mark.asyncio
    async def test_get_provider_config_prefers_groq(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-key", "GROQ_MODEL": "openai/gpt-oss-120b"}, clear=True):
            api_key, model, provider = _get_provider_config()
            assert provider == "groq"
            assert api_key == "groq-key"
            assert model == "openai/gpt-oss-120b"

    @pytest.mark.asyncio
    async def test_get_provider_config_uses_retirals_default_model(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-key"}, clear=True):
            api_key, model, provider = _get_provider_config()
            assert provider == "groq"
            assert api_key == "groq-key"
            assert model == "openai/gpt-oss-120b"

    def test_service_uses_groq_model_environment_override(self):
        with patch.dict(os.environ, {"GROQ_MODEL": "custom/model"}, clear=True):
            service = AIInsightService(settings=Settings(groq_api_key="test-key"))
            assert service.model == "custom/model"

    def test_service_uses_retirals_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            service = AIInsightService(settings=Settings(groq_api_key="test-key"))
            assert service.model == "openai/gpt-oss-120b"

    @pytest.mark.asyncio
    async def test_get_provider_config_falls_back_to_gemini(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-key", "GEMINI_MODEL": "gemini-2.0-flash"}, clear=True):
            api_key, model, provider = _get_provider_config()
            assert provider == "gemini"
            assert api_key == "gemini-key"

    @pytest.mark.asyncio
    async def test_get_provider_config_no_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                _get_provider_config()
