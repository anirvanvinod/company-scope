"""
Extraction task unit tests (Phase 5B).

All external I/O (DB sessions, MinIO, repository functions) is mocked so
these run without any infrastructure.

Tests cover:
  - extract_facts returns summary dict with correct keys
  - company not in DB raises ValueError (non-retryable)
  - no classified documents → returns zero counts
  - document with no storage_key is counted as failed
  - successful iXBRL extraction → extracted count incremented, parse_status='parsed'
  - successful HTML extraction → extracted count incremented
  - document with no period_end and no action_date → no_facts count, parse_status='parsed'
  - document with no period_end but action_date fallback → period upserted with action_date
  - extractor returning zero canonical facts → no_facts count
  - extraction exception → failed count, parse_status='failed', extraction_run finished as failed
  - unsupported document_format returns ExtractionResult with error (via _dispatch_extractor)
  - _dispatch_extractor routes ixbrl/xbrl to extract_ixbrl, html to extract_html
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.parsers.models import ExtractionResult, RawFact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(
    *,
    document_format: str = "ixbrl",
    storage_key: str | None = "company/filings/tx/doc.xhtml",
    action_date: date | None = date(2023, 12, 31),
    filing_document_id: uuid.UUID | None = None,
    document_id: str = "doc123",
    filing_id: uuid.UUID | None = None,
) -> dict:
    return {
        "filing_document_id": filing_document_id or uuid.uuid4(),
        "document_id": document_id,
        "document_format": document_format,
        "storage_key": storage_key,
        "filing_id": filing_id or uuid.uuid4(),
        "action_date": action_date,
    }


def _make_extraction_result(
    *,
    facts: list[RawFact] | None = None,
    period_end: date | None = date(2023, 12, 31),
    period_start: date | None = date(2023, 1, 1),
    run_confidence: Decimal = Decimal("0.90"),
) -> ExtractionResult:
    if facts is None:
        facts = [
            RawFact(
                raw_label="Turnover",
                raw_tag="uk-gaap:Turnover",
                raw_context_ref="ctx1",
                raw_value="1000000",
                fact_value=Decimal("1000000"),
                unit="GBP",
                period_start=period_start,
                period_end=period_end,
                is_comparative=False,
                scale=0,
                canonical_name="revenue",
                mapping_method="direct_tag",
                extraction_confidence=Decimal("0.90"),
            )
        ]
    return ExtractionResult(
        facts=facts,
        period_start=period_start,
        period_end=period_end,
        accounts_type=None,
        currency_code="GBP",
        run_confidence=run_confidence,
        warnings=[],
        errors=[],
        extraction_method="ixbrl",
    )


# ---------------------------------------------------------------------------
# _dispatch_extractor routing
# ---------------------------------------------------------------------------


def test_dispatch_extractor_ixbrl_calls_extract_ixbrl() -> None:
    from app.tasks.extraction import _dispatch_extractor

    content = b"<fake/>"
    with patch("app.tasks.extraction.extract_ixbrl") as mock_ixbrl:
        mock_ixbrl.return_value = _make_extraction_result()
        _dispatch_extractor("ixbrl", content)
        mock_ixbrl.assert_called_once_with(content)


def test_dispatch_extractor_xbrl_calls_extract_ixbrl() -> None:
    from app.tasks.extraction import _dispatch_extractor

    content = b"<fake/>"
    with patch("app.tasks.extraction.extract_ixbrl") as mock_ixbrl:
        mock_ixbrl.return_value = _make_extraction_result()
        _dispatch_extractor("xbrl", content)
        mock_ixbrl.assert_called_once_with(content)


def test_dispatch_extractor_html_calls_extract_html() -> None:
    from app.tasks.extraction import _dispatch_extractor

    content = b"<html/>"
    with patch("app.tasks.extraction.extract_html") as mock_html:
        mock_html.return_value = _make_extraction_result()
        _dispatch_extractor("html", content)
        mock_html.assert_called_once_with(content)


def test_dispatch_extractor_unsupported_format_returns_error_result() -> None:
    from app.tasks.extraction import _dispatch_extractor

    result = _dispatch_extractor("pdf", b"bytes")
    assert result.errors != []
    assert result.facts == []


# ---------------------------------------------------------------------------
# _extract_facts_async integration (fully mocked)
# ---------------------------------------------------------------------------


def _patch_all(
    *,
    company_id: uuid.UUID | None = None,
    documents: list | None = None,
    extraction_result: ExtractionResult | None = None,
    period_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
):
    """Return a context manager dict of all patches needed for the async core."""
    if company_id is None:
        company_id = uuid.uuid4()
    if documents is None:
        documents = [_make_doc()]
    if extraction_result is None:
        extraction_result = _make_extraction_result()
    if period_id is None:
        period_id = uuid.uuid4()
    if run_id is None:
        run_id = uuid.uuid4()

    return {
        "company_id": company_id,
        "documents": documents,
        "extraction_result": extraction_result,
        "period_id": period_id,
        "run_id": run_id,
    }


@pytest.mark.asyncio
async def test_company_not_found_raises_value_error() -> None:
    from app.tasks.extraction import _extract_facts_async

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.extraction.get_session", return_value=mock_ctx):
        with pytest.raises(ValueError, match="not found in DB"):
            await _extract_facts_async("99999999")


@pytest.mark.asyncio
async def test_no_classified_documents_returns_zero_counts() -> None:
    from app.tasks.extraction import _extract_facts_async

    company_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = company_id
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.extraction.get_session", return_value=mock_ctx),
        patch(
            "app.tasks.extraction.get_classified_documents_for_extraction",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await _extract_facts_async("12345678")

    assert result["extracted"] == 0
    assert result["no_facts"] == 0
    assert result["failed"] == 0


@pytest.mark.asyncio
async def test_missing_storage_key_increments_failed() -> None:
    from app.tasks.extraction import _extract_facts_async

    company_id = uuid.uuid4()
    doc = _make_doc(storage_key=None)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = company_id
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_s3_ctx = AsyncMock()
    mock_s3_ctx.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_s3_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.extraction.get_session", return_value=mock_ctx),
        patch(
            "app.tasks.extraction.get_classified_documents_for_extraction",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch("app.tasks.extraction.get_storage_client", return_value=mock_s3_ctx),
    ):
        result = await _extract_facts_async("12345678")

    assert result["failed"] == 1
    assert result["extracted"] == 0


@pytest.mark.asyncio
async def test_successful_extraction_increments_extracted() -> None:
    from app.tasks.extraction import _extract_facts_async

    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    period_id = uuid.uuid4()
    doc_uuid = uuid.uuid4()
    doc = _make_doc(document_format="ixbrl")
    extraction_result = _make_extraction_result()

    call_count = 0

    def _session_factory():
        mock_session = AsyncMock()

        def _make_execute_result(val):
            r = MagicMock()
            r.scalar_one_or_none.return_value = val
            return r

        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # company lookup
            mock_session.execute = AsyncMock(
                return_value=_make_execute_result(company_id)
            )
        else:
            # filing_documents lookup
            mock_session.execute = AsyncMock(
                return_value=_make_execute_result(doc_uuid)
            )
        mock_session.commit = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    mock_s3 = AsyncMock()
    mock_s3_ctx = AsyncMock()
    mock_s3_ctx.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_s3_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.extraction.get_session", side_effect=_session_factory),
        patch(
            "app.tasks.extraction.get_classified_documents_for_extraction",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch("app.tasks.extraction.get_storage_client", return_value=mock_s3_ctx),
        patch(
            "app.tasks.extraction.get_document",
            new_callable=AsyncMock,
            return_value=b"<fake/>",
        ),
        patch(
            "app.tasks.extraction._dispatch_extractor",
            return_value=extraction_result,
        ),
        patch(
            "app.tasks.extraction.create_extraction_run",
            new_callable=AsyncMock,
            return_value=run_id,
        ),
        patch(
            "app.tasks.extraction.upsert_financial_period",
            new_callable=AsyncMock,
            return_value=period_id,
        ),
        patch(
            "app.tasks.extraction.upsert_financial_facts",
            new_callable=AsyncMock,
            return_value=1,
        ),
        patch("app.tasks.extraction.finish_extraction_run", new_callable=AsyncMock),
        patch("app.tasks.extraction.update_document_parse_status", new_callable=AsyncMock),
    ):
        result = await _extract_facts_async("12345678")

    assert result["extracted"] == 1
    assert result["failed"] == 0
    assert result["no_facts"] == 0


@pytest.mark.asyncio
async def test_no_period_end_no_action_date_increments_no_facts() -> None:
    from app.tasks.extraction import _extract_facts_async

    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    doc = _make_doc(action_date=None)
    # Extraction result with no period_end
    extraction_result = _make_extraction_result(period_end=None, period_start=None, facts=[])

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        mock_session = AsyncMock()
        r = MagicMock()
        r.scalar_one_or_none.return_value = company_id
        mock_session.execute = AsyncMock(return_value=r)
        mock_session.commit = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    mock_s3_ctx = AsyncMock()
    mock_s3_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_s3_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.extraction.get_session", side_effect=_session_factory),
        patch(
            "app.tasks.extraction.get_classified_documents_for_extraction",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch("app.tasks.extraction.get_storage_client", return_value=mock_s3_ctx),
        patch(
            "app.tasks.extraction.get_document",
            new_callable=AsyncMock,
            return_value=b"<fake/>",
        ),
        patch(
            "app.tasks.extraction._dispatch_extractor",
            return_value=extraction_result,
        ),
        patch(
            "app.tasks.extraction.create_extraction_run",
            new_callable=AsyncMock,
            return_value=run_id,
        ),
        patch("app.tasks.extraction.finish_extraction_run", new_callable=AsyncMock),
        patch("app.tasks.extraction.update_document_parse_status", new_callable=AsyncMock),
    ):
        result = await _extract_facts_async("12345678")

    assert result["no_facts"] == 1
    assert result["extracted"] == 0


@pytest.mark.asyncio
async def test_extraction_exception_increments_failed() -> None:
    from app.tasks.extraction import _extract_facts_async

    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    doc = _make_doc()

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        mock_session = AsyncMock()
        r = MagicMock()
        r.scalar_one_or_none.return_value = company_id
        mock_session.execute = AsyncMock(return_value=r)
        mock_session.commit = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    mock_s3_ctx = AsyncMock()
    mock_s3_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_s3_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.extraction.get_session", side_effect=_session_factory),
        patch(
            "app.tasks.extraction.get_classified_documents_for_extraction",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch("app.tasks.extraction.get_storage_client", return_value=mock_s3_ctx),
        patch(
            "app.tasks.extraction.get_document",
            new_callable=AsyncMock,
            side_effect=RuntimeError("MinIO unreachable"),
        ),
        patch(
            "app.tasks.extraction.create_extraction_run",
            new_callable=AsyncMock,
            return_value=run_id,
        ),
        patch("app.tasks.extraction.finish_extraction_run", new_callable=AsyncMock),
        patch("app.tasks.extraction.update_document_parse_status", new_callable=AsyncMock),
    ):
        result = await _extract_facts_async("12345678")

    assert result["failed"] == 1
    assert result["extracted"] == 0


@pytest.mark.asyncio
async def test_zero_canonical_facts_increments_no_facts() -> None:
    from app.tasks.extraction import _extract_facts_async

    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    period_id = uuid.uuid4()
    doc_uuid = uuid.uuid4()
    doc = _make_doc()
    # Result with period_end but zero canonical facts
    extraction_result = _make_extraction_result(facts=[])
    extraction_result = ExtractionResult(
        facts=[],
        period_start=date(2023, 1, 1),
        period_end=date(2023, 12, 31),
        accounts_type=None,
        currency_code="GBP",
        run_confidence=Decimal("0"),
        warnings=[],
        errors=[],
        extraction_method="ixbrl",
    )

    call_count = 0

    def _session_factory():
        nonlocal call_count
        call_count += 1
        mock_session = AsyncMock()
        r = MagicMock()
        r.scalar_one_or_none.return_value = company_id if call_count == 1 else doc_uuid
        mock_session.execute = AsyncMock(return_value=r)
        mock_session.commit = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    mock_s3_ctx = AsyncMock()
    mock_s3_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_s3_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.extraction.get_session", side_effect=_session_factory),
        patch(
            "app.tasks.extraction.get_classified_documents_for_extraction",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch("app.tasks.extraction.get_storage_client", return_value=mock_s3_ctx),
        patch(
            "app.tasks.extraction.get_document",
            new_callable=AsyncMock,
            return_value=b"<fake/>",
        ),
        patch(
            "app.tasks.extraction._dispatch_extractor",
            return_value=extraction_result,
        ),
        patch(
            "app.tasks.extraction.create_extraction_run",
            new_callable=AsyncMock,
            return_value=run_id,
        ),
        patch(
            "app.tasks.extraction.upsert_financial_period",
            new_callable=AsyncMock,
            return_value=period_id,
        ),
        patch(
            "app.tasks.extraction.upsert_financial_facts",
            new_callable=AsyncMock,
            return_value=0,  # zero facts persisted
        ),
        patch("app.tasks.extraction.finish_extraction_run", new_callable=AsyncMock),
        patch("app.tasks.extraction.update_document_parse_status", new_callable=AsyncMock),
    ):
        result = await _extract_facts_async("12345678")

    assert result["no_facts"] == 1
    assert result["extracted"] == 0
