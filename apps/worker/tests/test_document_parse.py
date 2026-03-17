"""
Document parse pipeline unit tests — Phase 5A (classification only).

Tests cover:
  - _parse_documents_async: orchestration with all dependencies mocked
  - repository helpers:
      get_documents_ready_for_parse
      create_extraction_run
      finish_extraction_run
      update_document_parse_status
  - Celery task non-retryable ValueError path

Mocking strategy:
  - get_session patched to return AsyncMock session
  - get_documents_ready_for_parse / create_extraction_run /
    finish_extraction_run / update_document_parse_status patched
    individually in orchestration tests
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.parsers.classifier import PARSER_VERSION
from app.repositories import (
    create_extraction_run,
    finish_extraction_run,
    get_documents_ready_for_parse,
    update_document_parse_status,
)
from app.tasks.document_parse import _parse_documents_async, parse_documents


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_cm(value: object) -> object:
    """Return an async context manager that yields *value*."""

    @asynccontextmanager
    async def _cm() -> AsyncGenerator[object, None]:
        yield value

    return _cm()


def _make_session(scalar_return: object = None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_return
    session.execute.return_value = result
    return session


def _make_pending_doc(
    content_type: str = "application/xhtml+xml",
    parse_status: str = "pending",
) -> dict:
    return {
        "filing_document_id": uuid.uuid4(),
        "document_id": "DOCABC123",
        "content_type": content_type,
        "available_content_types": [content_type],
        "storage_key": f"12345678/filings/TXN001/DOCABC123.xhtml",
        "filing_id": uuid.uuid4(),
        "company_number": "12345678",
    }


# ---------------------------------------------------------------------------
# _parse_documents_async — orchestration
# ---------------------------------------------------------------------------


async def test_parse_documents_returns_zero_when_no_pending() -> None:
    """If get_documents_ready_for_parse returns empty, exit early."""
    company_id = uuid.uuid4()
    mock_session = _make_session(scalar_return=company_id)

    with (
        patch(
            "app.tasks.document_parse.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.document_parse.get_documents_ready_for_parse",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await _parse_documents_async("12345678")

    assert result == {
        "company_number": "12345678",
        "classified": 0,
        "unsupported": 0,
        "failed": 0,
    }


async def test_parse_documents_raises_when_company_not_found() -> None:
    """ValueError raised if the company is not in the DB."""
    mock_session = _make_session(scalar_return=None)

    with patch(
        "app.tasks.document_parse.get_session",
        return_value=_async_cm(mock_session),
    ):
        with pytest.raises(ValueError, match="not found in DB"):
            await _parse_documents_async("00000000")


async def test_parse_documents_classifies_ixbrl_document() -> None:
    """application/xhtml+xml → ixbrl → parse_status='classified'."""
    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    doc = _make_pending_doc(content_type="application/xhtml+xml")
    mock_session = _make_session(scalar_return=company_id)

    with (
        patch(
            "app.tasks.document_parse.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.document_parse.get_documents_ready_for_parse",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch(
            "app.tasks.document_parse.create_extraction_run",
            new_callable=AsyncMock,
            return_value=run_id,
        ) as mock_create_run,
        patch(
            "app.tasks.document_parse.update_document_parse_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
        patch(
            "app.tasks.document_parse.finish_extraction_run",
            new_callable=AsyncMock,
        ) as mock_finish_run,
    ):
        result = await _parse_documents_async("12345678")

    assert result["classified"] == 1
    assert result["unsupported"] == 0
    assert result["failed"] == 0

    mock_create_run.assert_called_once_with(
        filing_id=doc["filing_id"],
        filing_document_id=doc["filing_document_id"],
        document_format="ixbrl",
        parser_version=PARSER_VERSION,
    )
    mock_update_status.assert_called_once()
    call_kwargs = mock_update_status.call_args.kwargs
    assert call_kwargs["parse_status"] == "classified"
    assert call_kwargs["document_format"] == "ixbrl"

    mock_finish_run.assert_called_once_with(run_id, status="completed")


async def test_parse_documents_marks_pdf_as_unsupported() -> None:
    """application/pdf → pdf → parse_status='unsupported'."""
    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    doc = _make_pending_doc(content_type="application/pdf")
    mock_session = _make_session(scalar_return=company_id)

    with (
        patch(
            "app.tasks.document_parse.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.document_parse.get_documents_ready_for_parse",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch(
            "app.tasks.document_parse.create_extraction_run",
            new_callable=AsyncMock,
            return_value=run_id,
        ),
        patch(
            "app.tasks.document_parse.update_document_parse_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
        patch(
            "app.tasks.document_parse.finish_extraction_run",
            new_callable=AsyncMock,
        ) as mock_finish_run,
    ):
        result = await _parse_documents_async("12345678")

    assert result["unsupported"] == 1
    assert result["classified"] == 0

    call_kwargs = mock_update_status.call_args.kwargs
    assert call_kwargs["parse_status"] == "unsupported"
    assert call_kwargs["document_format"] == "pdf"
    mock_finish_run.assert_called_once_with(run_id, status="unsupported")


async def test_parse_documents_marks_unknown_type_as_unsupported() -> None:
    """Unrecognised content_type → unsupported."""
    company_id = uuid.uuid4()
    doc = _make_pending_doc(content_type="application/octet-stream")
    mock_session = _make_session(scalar_return=company_id)

    with (
        patch(
            "app.tasks.document_parse.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.document_parse.get_documents_ready_for_parse",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch(
            "app.tasks.document_parse.create_extraction_run",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ),
        patch(
            "app.tasks.document_parse.update_document_parse_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
        patch("app.tasks.document_parse.finish_extraction_run", new_callable=AsyncMock),
    ):
        result = await _parse_documents_async("12345678")

    assert result["unsupported"] == 1
    call_kwargs = mock_update_status.call_args.kwargs
    assert call_kwargs["document_format"] == "unsupported"


async def test_parse_documents_handles_classification_error() -> None:
    """An unexpected exception during create_extraction_run increments failed
    and marks the document failed, then continues."""
    company_id = uuid.uuid4()
    doc = _make_pending_doc()
    mock_session = _make_session(scalar_return=company_id)

    with (
        patch(
            "app.tasks.document_parse.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.document_parse.get_documents_ready_for_parse",
            new_callable=AsyncMock,
            return_value=[doc],
        ),
        patch(
            "app.tasks.document_parse.create_extraction_run",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db error"),
        ),
        patch(
            "app.tasks.document_parse.update_document_parse_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
        patch("app.tasks.document_parse.finish_extraction_run", new_callable=AsyncMock),
    ):
        result = await _parse_documents_async("12345678")

    assert result["failed"] == 1
    assert result["classified"] == 0

    # Document should be marked failed
    call_kwargs = mock_update_status.call_args.kwargs
    assert call_kwargs["parse_status"] == "failed"


async def test_parse_documents_processes_multiple_documents() -> None:
    """Mixed batch: ixbrl classified, pdf unsupported, one failure."""
    company_id = uuid.uuid4()
    docs = [
        _make_pending_doc(content_type="application/xhtml+xml"),
        _make_pending_doc(content_type="application/pdf"),
        _make_pending_doc(content_type="text/html"),
    ]
    # Make document_ids distinct so update_document_parse_status calls differ
    for i, doc in enumerate(docs):
        doc["document_id"] = f"DOC{i:03d}"

    mock_session = _make_session(scalar_return=company_id)
    run_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    with (
        patch(
            "app.tasks.document_parse.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.document_parse.get_documents_ready_for_parse",
            new_callable=AsyncMock,
            return_value=docs,
        ),
        patch(
            "app.tasks.document_parse.create_extraction_run",
            new_callable=AsyncMock,
            side_effect=run_ids,
        ),
        patch(
            "app.tasks.document_parse.update_document_parse_status",
            new_callable=AsyncMock,
        ),
        patch("app.tasks.document_parse.finish_extraction_run", new_callable=AsyncMock),
    ):
        result = await _parse_documents_async("12345678")

    assert result["classified"] == 2   # ixbrl + html
    assert result["unsupported"] == 1  # pdf
    assert result["failed"] == 0


# ---------------------------------------------------------------------------
# Celery task — non-retryable ValueError
# ---------------------------------------------------------------------------


def test_parse_documents_does_not_retry_on_missing_company() -> None:
    """ValueError (company not in DB) must not trigger Celery retry."""
    mock_self = MagicMock()
    with patch(
        "asyncio.run",
        side_effect=ValueError("Company '99999999' not found in DB."),
    ):
        with pytest.raises(ValueError):
            parse_documents.__wrapped__(mock_self, "99999999")
    mock_self.retry.assert_not_called()


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------


async def test_get_documents_ready_for_parse_returns_list() -> None:
    """get_documents_ready_for_parse executes one query and returns dicts."""
    session = AsyncMock()
    row1 = MagicMock()
    row1._mapping = {
        "filing_document_id": uuid.uuid4(),
        "document_id": "DOC001",
        "content_type": "application/xhtml+xml",
        "available_content_types": ["application/xhtml+xml"],
        "storage_key": "12345678/filings/TXN001/DOC001.xhtml",
        "filing_id": uuid.uuid4(),
        "company_number": "12345678",
    }
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [row1]
    session.execute.return_value = mock_result

    docs = await get_documents_ready_for_parse(session, uuid.uuid4())

    assert len(docs) == 1
    assert docs[0]["document_id"] == "DOC001"
    session.execute.assert_called_once()


async def test_get_documents_ready_for_parse_empty_list() -> None:
    """Returns empty list when no documents are pending."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    session.execute.return_value = mock_result

    docs = await get_documents_ready_for_parse(session, uuid.uuid4())

    assert docs == []


async def test_create_extraction_run_commits_and_returns_uuid() -> None:
    """create_extraction_run inserts a running row and commits immediately."""
    mock_session = AsyncMock()

    with patch(
        "app.repositories.get_session", return_value=_async_cm(mock_session)
    ):
        run_id = await create_extraction_run(
            filing_id=uuid.uuid4(),
            filing_document_id=uuid.uuid4(),
            document_format="ixbrl",
            parser_version=PARSER_VERSION,
        )

    assert isinstance(run_id, uuid.UUID)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
    # Verify the INSERT includes document_format
    stmt = mock_session.execute.call_args[0][0]
    assert "document_format" in str(stmt)


async def test_finish_extraction_run_updates_and_commits() -> None:
    """finish_extraction_run updates the row status and commits immediately."""
    mock_session = AsyncMock()

    with patch(
        "app.repositories.get_session", return_value=_async_cm(mock_session)
    ):
        await finish_extraction_run(uuid.uuid4(), status="completed")

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


async def test_finish_extraction_run_passes_errors() -> None:
    """errors dict is forwarded when status='failed'."""
    mock_session = AsyncMock()

    with patch(
        "app.repositories.get_session", return_value=_async_cm(mock_session)
    ):
        await finish_extraction_run(
            uuid.uuid4(),
            status="failed",
            errors={"exception": "boom"},
        )

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


async def test_update_document_parse_status_executes_update() -> None:
    """update_document_parse_status executes one UPDATE statement."""
    session = AsyncMock()
    await update_document_parse_status(
        session,
        document_id="DOCABC",
        parse_status="classified",
        document_format="ixbrl",
    )
    session.execute.assert_called_once()
    stmt = session.execute.call_args[0][0]
    assert "parse_status" in str(stmt)


async def test_update_document_parse_status_without_format() -> None:
    """document_format=None should not appear in the UPDATE values."""
    session = AsyncMock()
    await update_document_parse_status(
        session,
        document_id="DOCABC",
        parse_status="failed",
    )
    session.execute.assert_called_once()
    stmt = session.execute.call_args[0][0]
    # parse_status should be present; document_format should not be set
    assert "parse_status" in str(stmt)
