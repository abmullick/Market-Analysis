from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Literal

from groq import Groq, RateLimitError, APIStatusError, APIConnectionError
from google import genai
from google.genai import errors
from pydantic import BaseModel, Field, ValidationError

from backend.config.settings import Settings
from backend.utils.logging import logger

logger = logging.getLogger(__name__)


class InsightRequest(BaseModel):
    data: dict[str, Any] = Field(..., description="Structured fund/portfolio/stock data for AI analysis.")
    context: str = Field(default="fund_analysis", description="Analysis context: fund_analysis, portfolio_analysis, ranking_summary.")
    focus: str | None = Field(default=None, description="Optional specific focus area for the insight.")


class InsightResponse(BaseModel):
    summary: str = Field(..., description="One-paragraph executive summary of the analysis.")
    key_points: list[str] = Field(default_factory=list, description="Bullet-style key takeaways from the data.")
    risks: list[str] = Field(default_factory=list, description="Identified risks or concerns from the analysis.")
    opportunities: list[str] = Field(default_factory=list, description="Identified opportunities or strengths.")
    recommendation: str | None = Field(default=None, description="Suggested action or next step based on the analysis.")


SYSTEM_INSTRUCTION = """You are a financial analysis assistant for an Indian market analysis platform.
Your job is to interpret structured fund/portfolio data, identify meaningful patterns, and provide clear, evidence-based insights.

RULES
1. NUMERICAL INTEGRITY: Never invent, calculate, derive, or estimate numbers. Only reference values explicitly present in the supplied data. If a number is not in the data, use qualitative language instead.
2. CONTEXT AWARENESS: Use the `context` field to understand what type of data is being analyzed (fund_analysis, portfolio_analysis, ranking_summary). Tailor your insights accordingly.
3. CLARITY: Write in clear, plain language suitable for retail investors. Avoid jargon where possible, but use standard financial terms when precise.
4. BALANCE: Highlight both strengths and risks. Do not be overly bullish or bearish. Every analysis should mention at least one strength and one risk when the data supports it.
5. ACTIONABILITY: When possible, connect insights to concrete next steps the user could consider, grounded in the supplied data.
6. JSON ONLY: Return ONLY the JSON object matching the InsightResponse schema. No Markdown, no code fences, no explanatory text before or after.
"""


def _get_groq_config() -> tuple[str, str]:
    api_key = os.environ.get("GROQ_API_KEY") or Settings().groq_api_key
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set.")
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    return api_key, model


def _get_gemini_config() -> tuple[str, str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    return api_key, model


def _get_provider_config() -> tuple[str, str, str]:
    groq_key = os.environ.get("GROQ_API_KEY") or Settings().groq_api_key
    if groq_key:
        model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
        return groq_key, model, "groq"
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        return gemini_key, model, "gemini"
    raise ValueError("Either GROQ_API_KEY or GEMINI_API_KEY must be set.")


def _extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    start = text.find("{")
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text, start)
            return obj
        except json.JSONDecodeError:
            pass
    return json.loads(text)


def _repair_insight_response(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {}
    defaults: dict[str, Any] = {
        "summary": "",
        "key_points": [],
        "risks": [],
        "opportunities": [],
        "recommendation": None,
    }
    for key, default in defaults.items():
        if key not in parsed or parsed[key] is None:
            parsed[key] = default
    return parsed


def _is_rate_limited(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code not in (429, 413):
        return False
    text = str(exc).lower()
    quota_markers = [
        "quota exceeded",
        "rate_limit",
        "rate-limit",
        "too many requests",
        "daily limit",
        "monthly limit",
        "free tier",
        "freetier",
        "tokens per minute",
        "tpm",
        "request too large",
        "rate_limit_exceeded",
    ]
    return any(marker in text for marker in quota_markers)


async def _call_groq(api_key: str, model_name: str, prompt: str) -> InsightResponse:
    client = Groq(api_key=api_key)
    max_retries = 2
    base_delay = 1.0
    last_exception = None

    schema = InsightResponse.model_json_schema()
    schema["additionalProperties"] = False
    schema_str = json.dumps(schema)

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "InsightResponse",
                        "schema": schema,
                        "strict": False,
                    },
                },
                max_completion_tokens=4096,
                temperature=0.3,
            )
            raw_text = response.choices[0].message.content or ""
            if not raw_text.strip():
                raise ValueError("Groq returned an empty response.")
            parsed = _extract_json_from_text(raw_text)
            parsed = _repair_insight_response(parsed)
            return InsightResponse(**parsed)
        except (RateLimitError, APIConnectionError) as exc:
            last_exception = exc
            if _is_rate_limited(exc):
                break
            if attempt == max_retries:
                break
            await asyncio.sleep(base_delay * (2 ** attempt))
        except APIStatusError as exc:
            last_exception = exc
            status_code = getattr(exc, "status_code", None)
            retryable = status_code == 429 or (isinstance(status_code, int) and status_code >= 500)
            if not retryable or attempt == max_retries:
                break
            await asyncio.sleep(base_delay * (2 ** attempt))
        except Exception as exc:
            last_exception = exc
            break

    if last_exception:
        raise last_exception
    raise RuntimeError("An unexpected error occurred while processing AI insight request.")


async def _call_gemini(api_key: str, model_name: str, prompt: str) -> InsightResponse:
    client = genai.Client(api_key=api_key)
    max_retries = 2
    base_delay = 1.0
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=InsightResponse,
                    temperature=0.3,
                    max_output_tokens=4096,
                ),
            )
            raw_text = response.text or ""
            if not raw_text.strip():
                raise ValueError("Gemini returned an empty response.")
            parsed = _extract_json_from_text(raw_text)
            return InsightResponse(**parsed)
        except genai.errors.APIError as exc:
            last_exception = exc
            status_code = getattr(exc, "code", None)
            retryable = status_code == 429 or (isinstance(status_code, int) and status_code >= 500)
            if not retryable or attempt == max_retries:
                break
            await asyncio.sleep(base_delay * (2 ** attempt))
        except Exception as exc:
            last_exception = exc
            break

    if last_exception:
        raise last_exception
    raise RuntimeError("An unexpected error occurred while processing AI insight request.")


def _build_prompt(request: InsightRequest) -> str:
    payload = request.model_dump(mode="json")
    return json.dumps(payload, indent=2)


class AIInsightService:
    def __init__(self, settings: Settings):
        self.api_key = settings.groq_api_key
        self.model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    async def generate_insights(self, data: dict[str, Any], context: str = "fund_analysis", focus: str | None = None) -> InsightResponse:
        request = InsightRequest(data=data, context=context, focus=focus)
        return await self.process_insight_request(request)

    @staticmethod
    async def process_insight_request(request: InsightRequest) -> InsightResponse:
        api_key, model_name, provider = _get_provider_config()
        prompt = _build_prompt(request)
        try:
            if provider == "gemini":
                response = await _call_gemini(api_key, model_name, prompt)
            else:
                response = await _call_groq(api_key, model_name, prompt)
            return response
        except (RateLimitError, APIConnectionError, APIStatusError) as exc:
            logger.error("Groq API error: %s", exc, exc_info=True)
            raise RuntimeError("The AI service is temporarily unavailable. Please try again later.") from exc
        except genai.errors.APIError as exc:
            logger.error("Gemini API error: %s", exc, exc_info=True)
            raise RuntimeError("The AI service is temporarily unavailable. Please try again later.") from exc
        except ValidationError as exc:
            logger.error("AI insight validation error: %s", exc, exc_info=True)
            raise RuntimeError("The AI service returned an invalid response. Please try again.") from exc
        except RuntimeError:
            raise
        except Exception:
            logger.error("An unexpected error occurred during AI insight processing.", exc_info=True)
            raise RuntimeError("The AI service is temporarily unavailable. Please try again later.") from None
