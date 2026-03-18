"""
Tests for the Phase 6B snapshot builder.

Coverage:
- Template summary used when ai_enabled=false
- Template summary used when AI call raises AICallFailed
- AI summary used when ai_enabled=true and call succeeds
- Snapshot payload contains required fields
- Snapshot payload methodology_version matches METHODOLOGY_VERSION
- Snapshot payload summary_source is "ai" or "template"
- model_version is empty string for template source
- model_version is model name for ai source

All DB access and AI calls are mocked.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.analytics.ai_models import (
    AISummaryOutput,
    AnalysisContext,
    CompanyInfo,
    DataQualityInfo,
    PrimaryPeriodInfo,
)
from app.analytics.metrics import METHODOLOGY_VERSION
from app.analytics.models import PeriodSnapshot
from datetime import date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_period() -> PeriodSnapshot:
    return PeriodSnapshot(
        period_id=uuid.UUID("cccccccc-0000-0000-0000-000000000001"),
        period_end=date(2023, 12, 31),
        period_start=date(2023, 1, 1),
        extraction_confidence=Decimal("0.90"),
        accounts_type="small",
    )


def _make_ctx() -> AnalysisContext:
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


def _make_ai_output(source: str = "ai") -> AISummaryOutput:
    return AISummaryOutput(
        summary_short="AI summary for Test Co Ltd.",
        source=source,
    )


COMPANY_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_template_used_when_ai_disabled():
    from app.analytics.snapshot_builder import build_company_snapshot

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=COMPANY_ID))
    )

    with (
        patch("app.analytics.snapshot_builder.get_primary_period_for_analysis", new=AsyncMock(return_value=_make_period())),
        patch("app.analytics.snapshot_builder.get_prior_period_for_analysis", new=AsyncMock(return_value=None)),
        patch("app.analytics.snapshot_builder.build_analysis_context", new=AsyncMock(return_value=_make_ctx())),
        patch("app.analytics.snapshot_builder.settings") as mock_settings,
        patch("app.analytics.snapshot_builder.generate_template_summary", return_value=_make_ai_output("template")) as mock_template,
    ):
        mock_settings.ai_enabled = False
        mock_settings.ai_model_name = "mistral:7b-instruct"

        _, payload = await build_company_snapshot("01234567", mock_session)

    assert payload.summary_source == "template"
    assert payload.model_version == ""
    mock_template.assert_called_once()


@pytest.mark.asyncio
async def test_template_used_when_ai_call_fails():
    from app.analytics.snapshot_builder import build_company_snapshot
    from app.analytics.ai_client import AICallFailed

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=COMPANY_ID))
    )

    with (
        patch("app.analytics.snapshot_builder.get_primary_period_for_analysis", new=AsyncMock(return_value=_make_period())),
        patch("app.analytics.snapshot_builder.get_prior_period_for_analysis", new=AsyncMock(return_value=None)),
        patch("app.analytics.snapshot_builder.build_analysis_context", new=AsyncMock(return_value=_make_ctx())),
        patch("app.analytics.snapshot_builder.settings") as mock_settings,
        patch("app.analytics.snapshot_builder.generate_ai_summary", new=AsyncMock(side_effect=AICallFailed("timeout"))),
        patch("app.analytics.snapshot_builder.generate_template_summary", return_value=_make_ai_output("template")) as mock_template,
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"

        _, payload = await build_company_snapshot("01234567", mock_session)

    assert payload.summary_source == "template"
    mock_template.assert_called_once()


@pytest.mark.asyncio
async def test_ai_summary_used_when_call_succeeds():
    from app.analytics.snapshot_builder import build_company_snapshot

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=COMPANY_ID))
    )

    with (
        patch("app.analytics.snapshot_builder.get_primary_period_for_analysis", new=AsyncMock(return_value=_make_period())),
        patch("app.analytics.snapshot_builder.get_prior_period_for_analysis", new=AsyncMock(return_value=None)),
        patch("app.analytics.snapshot_builder.build_analysis_context", new=AsyncMock(return_value=_make_ctx())),
        patch("app.analytics.snapshot_builder.settings") as mock_settings,
        patch("app.analytics.snapshot_builder.generate_ai_summary", new=AsyncMock(return_value=_make_ai_output("ai"))),
    ):
        mock_settings.ai_enabled = True
        mock_settings.ai_model_name = "mistral:7b-instruct"

        _, payload = await build_company_snapshot("01234567", mock_session)

    assert payload.summary_source == "ai"
    assert payload.model_version == "mistral:7b-instruct"


@pytest.mark.asyncio
async def test_payload_contains_required_fields():
    from app.analytics.snapshot_builder import build_company_snapshot

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=COMPANY_ID))
    )

    with (
        patch("app.analytics.snapshot_builder.get_primary_period_for_analysis", new=AsyncMock(return_value=_make_period())),
        patch("app.analytics.snapshot_builder.get_prior_period_for_analysis", new=AsyncMock(return_value=None)),
        patch("app.analytics.snapshot_builder.build_analysis_context", new=AsyncMock(return_value=_make_ctx())),
        patch("app.analytics.snapshot_builder.settings") as mock_settings,
        patch("app.analytics.snapshot_builder.generate_template_summary", return_value=_make_ai_output("template")),
    ):
        mock_settings.ai_enabled = False
        mock_settings.ai_model_name = ""

        _, payload = await build_company_snapshot("01234567", mock_session)

    assert payload.company_number == "01234567"
    assert payload.methodology_version == METHODOLOGY_VERSION
    assert isinstance(payload.analysis_context, dict)
    assert isinstance(payload.ai_summary, dict)


@pytest.mark.asyncio
async def test_raises_value_error_when_company_not_found():
    from app.analytics.snapshot_builder import build_company_snapshot

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )

    with pytest.raises(ValueError, match="not found"):
        await build_company_snapshot("99999999", mock_session)


@pytest.mark.asyncio
async def test_raises_value_error_when_no_primary_period():
    from app.analytics.snapshot_builder import build_company_snapshot

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=COMPANY_ID))
    )

    with (
        patch("app.analytics.snapshot_builder.get_primary_period_for_analysis", new=AsyncMock(return_value=None)),
        patch("app.analytics.snapshot_builder.settings") as mock_settings,
    ):
        mock_settings.ai_enabled = False

        with pytest.raises(ValueError, match="No qualifying"):
            await build_company_snapshot("01234567", mock_session)
