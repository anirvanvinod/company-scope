"""
AI inference client for the Phase 6B analysis layer.

Entry point:
    generate_ai_summary(ctx: AnalysisContext, company_id, period_id)
        -> AISummaryOutput

Flow:
1. Build Redis cache key from (company_id, period_id, methodology_version, model).
2. Return cached AISummaryOutput if present.
3. POST to the local inference endpoint (OpenAI-compatible /v1/chat/completions).
4. Parse and schema-validate the JSON response.
5. Cache result for 24 hours.
6. On timeout, connection error, or schema failure: raise AICallFailed.
   The caller (snapshot_builder) catches this and invokes the template fallback.

The AI endpoint must be OpenAI-compatible (Ollama ≥0.1.24 and vLLM both expose
this by default). No data is sent to third-party hosted APIs.
"""

from __future__ import annotations

import json
import logging
import uuid

import httpx
import redis.asyncio as aioredis
from pydantic import ValidationError

from app.analytics.ai_models import AnalysisContext, AISummaryOutput
from app.analytics.metrics import METHODOLOGY_VERSION
from app.config import settings

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a structured financial data interpreter for a UK company intelligence platform.

Your job is to produce a concise, forensic, evidence-bound narrative summary of \
a UK company based exclusively on the structured data provided to you. You are not \
a financial advisor, investment analyst, or credit officer.

Rules you must always follow:
- Every statement you make must be directly traceable to a field in the input.
- Do not invent figures, trends, or context that are not in the input.
- Where data is marked null or unavailable, say so plainly. Do not fill gaps with assumptions.
- Do not recommend any course of action.
- Do not score the company.
- Do not predict future performance.
- Use plain, direct British English. Avoid marketing language.
- Where confidence is low or unavailable, state this limitation explicitly.
- Use past tense when referring to filed figures ("the company reported", "accounts showed").
- Flag data quality limitations at the end of the summary if they are material.

Output format: structured JSON matching the output schema provided.\
"""

_USER_PREFIX = "Analyse the following company data and produce a structured narrative summary.\n\n"

_CACHE_TTL_SECONDS = 86_400  # 24 hours


class AICallFailed(Exception):
    """Raised when the AI call cannot produce a valid response."""


def _cache_key(
    company_id: uuid.UUID,
    period_id: uuid.UUID,
    model: str,
) -> str:
    return (
        f"ai_summary:{company_id}:{period_id}"
        f":{METHODOLOGY_VERSION}:{model}"
    )


async def generate_ai_summary(
    ctx: AnalysisContext,
    company_id: uuid.UUID,
    period_id: uuid.UUID,
) -> AISummaryOutput:
    """
    Generate or retrieve from cache an AISummaryOutput for the given context.

    Raises AICallFailed on timeout, connection error, or schema violation.
    """
    if not settings.ai_enabled:
        raise AICallFailed("AI is disabled (ai_enabled=false)")

    model = settings.ai_model_name
    cache_key = _cache_key(company_id, period_id, model)

    # --- Redis cache check ---
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            log.debug("AI summary cache hit for %s", cache_key)
            return AISummaryOutput.model_validate_json(cached)
    except Exception as exc:
        log.warning("Redis cache read failed: %s — proceeding without cache", exc)
    finally:
        await redis_client.aclose()

    # --- AI inference call ---
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PREFIX + ctx.model_dump_json(indent=2),
            },
        ],
        "stream": False,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(
            base_url=settings.ai_inference_url,
            timeout=settings.ai_timeout_seconds,
        ) as client:
            response = await client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise AICallFailed(f"AI inference timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise AICallFailed(f"AI inference HTTP error: {exc}") from exc

    # --- Parse and validate response ---
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        raw = json.loads(content)
        raw["source"] = "ai"
        result = AISummaryOutput.model_validate(raw)
    except (KeyError, json.JSONDecodeError, ValidationError) as exc:
        raise AICallFailed(f"AI response schema invalid: {exc}") from exc

    # --- Cache result ---
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis_client.setex(
            cache_key,
            _CACHE_TTL_SECONDS,
            result.model_dump_json(),
        )
    except Exception as exc:
        log.warning("Redis cache write failed: %s — result not cached", exc)
    finally:
        await redis_client.aclose()

    log.info(
        "AI summary generated for company_id=%s period_id=%s model=%s",
        company_id,
        period_id,
        model,
    )
    return result
