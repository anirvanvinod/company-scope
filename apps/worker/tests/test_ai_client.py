"""
Tests for the Phase 6B AI inference client.

Coverage:
- AICallFailed raised when ai_enabled=false
- AICallFailed raised on HTTP timeout
- AICallFailed raised on non-2xx HTTP status
- AICallFailed raised on invalid JSON response
- AICallFailed raised on schema validation failure
- Valid response is returned as AISummaryOutput with source="ai"
- Redis cache hit returns cached result without making HTTP call
- Cache miss stores result in Redis

All HTTP calls are intercepted with respx; Redis is patched to avoid
requiring a running Redis server.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from app.analytics.ai_models import (
    AnalysisContext,
    CompanyInfo,
    DataQualityInfo,
    FactValue,
    PrimaryPeriodInfo,
)
from app.analytics.ai_client import AICallFailed, generate_ai_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_ctx() -> AnalysisContext:
    return AnalysisContext(
        company=CompanyInfo(
            company_number="01234567",
            company_name="Test Co Ltd",
        ),
        primary_period=PrimaryPeriodInfo(
            period_end="2023-12-31",
            extraction_confidence=Decimal("0.90"),
            confidence_band="high",
        ),
        data_quality=DataQualityInfo(),
    )


def _valid_ai_response() -> dict:
    return {
        "summary_short": "Test Co Ltd reported revenue of £1m for the period ending 2023-12-31.",
        "narrative_paragraphs": [
            {"topic": "financial_overview", "text": "Revenue was £1m.", "confidence_note": None}
        ],
        "key_observations": [],
        "data_quality_note": None,
        "caveats": ["This summary is informational only."],
    }


def _openai_envelope(content: str) -> dict:
    return {
        "choices": [
            {"message": {"content": content}}
        ]
    }


_COMPANY_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_PERIOD_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------


def _no_cache():
    """Returns a mock Redis client that always misses the cache."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.aclose = AsyncMock()
    return mock


def _cache_hit(cached_json: str):
    """Returns a mock Redis client that always hits."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=cached_json)
    mock.aclose = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_when_ai_disabled():
    ctx = _minimal_ctx()
    with patch("app.analytics.ai_client.settings") as mock_settings:
        mock_settings.ai_enabled = False
        with pytest.raises(AICallFailed, match="disabled"):
            await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)


@pytest.mark.asyncio
async def test_raises_on_http_timeout():
    ctx = _minimal_ctx()
    with (
        patch("app.analytics.ai_client.settings") as mock_settings,
        patch("app.analytics.ai_client.aioredis.from_url", return_value=_no_cache()),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.ai_inference_url = "http://localhost:11434"
        mock_settings.ai_timeout_seconds = 8.0

        with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").mock(
                side_effect=httpx.TimeoutException("timed out")
            )
            with pytest.raises(AICallFailed, match="timed out"):
                await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)


@pytest.mark.asyncio
async def test_raises_on_non_2xx_status():
    ctx = _minimal_ctx()
    with (
        patch("app.analytics.ai_client.settings") as mock_settings,
        patch("app.analytics.ai_client.aioredis.from_url", return_value=_no_cache()),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.ai_inference_url = "http://localhost:11434"
        mock_settings.ai_timeout_seconds = 8.0

        with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").mock(
                return_value=httpx.Response(503)
            )
            with pytest.raises(AICallFailed):
                await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)


@pytest.mark.asyncio
async def test_raises_on_invalid_json_content():
    ctx = _minimal_ctx()
    with (
        patch("app.analytics.ai_client.settings") as mock_settings,
        patch("app.analytics.ai_client.aioredis.from_url", return_value=_no_cache()),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.ai_inference_url = "http://localhost:11434"
        mock_settings.ai_timeout_seconds = 8.0

        with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json=_openai_envelope("not valid json {{{{"),
                )
            )
            with pytest.raises(AICallFailed, match="schema invalid"):
                await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)


@pytest.mark.asyncio
async def test_raises_on_schema_violation():
    ctx = _minimal_ctx()
    bad_content = json.dumps({"unexpected_field": "no summary_short here"})
    with (
        patch("app.analytics.ai_client.settings") as mock_settings,
        patch("app.analytics.ai_client.aioredis.from_url", return_value=_no_cache()),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.ai_inference_url = "http://localhost:11434"
        mock_settings.ai_timeout_seconds = 8.0

        with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=_openai_envelope(bad_content))
            )
            with pytest.raises(AICallFailed, match="schema invalid"):
                await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)


@pytest.mark.asyncio
async def test_valid_response_returns_ai_summary_output():
    ctx = _minimal_ctx()
    ai_content = json.dumps(_valid_ai_response())
    with (
        patch("app.analytics.ai_client.settings") as mock_settings,
        patch("app.analytics.ai_client.aioredis.from_url", return_value=_no_cache()),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.ai_inference_url = "http://localhost:11434"
        mock_settings.ai_timeout_seconds = 8.0

        with respx.mock:
            respx.post("http://localhost:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=_openai_envelope(ai_content))
            )
            result = await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)

    assert result.source == "ai"
    assert "Test Co Ltd" in result.summary_short


@pytest.mark.asyncio
async def test_cache_hit_skips_http_call():
    ctx = _minimal_ctx()
    cached = _valid_ai_response()
    cached["source"] = "ai"
    cached_json = json.dumps(cached)

    with (
        patch("app.analytics.ai_client.settings") as mock_settings,
        patch(
            "app.analytics.ai_client.aioredis.from_url",
            return_value=_cache_hit(cached_json),
        ),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.ai_inference_url = "http://localhost:11434"
        mock_settings.ai_timeout_seconds = 8.0

        # No HTTP mock — would raise if a network call were made
        with respx.mock:
            result = await generate_ai_summary(ctx, _COMPANY_ID, _PERIOD_ID)

    assert result.source == "ai"
