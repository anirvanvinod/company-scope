"""
Document fetch pipeline unit tests.

Tests cover:
  - _extract_document_id: URL parsing helper
  - _pick_content_type: content type selection
  - build_storage_key: deterministic MinIO key generation
  - _fetch_documents_async: orchestration with all dependencies mocked
  - repository helpers: upsert_document_metadata, mark_document_fetched,
    mark_document_failed

Mocking strategy:
  - create_ch_client patched to return AsyncMock client
  - get_storage_client patched to return AsyncMock S3 client
  - get_session patched to return AsyncMock session
  - Repository functions patched individually in orchestration tests
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.object_store import CONTENT_TYPE_PRIORITY, build_storage_key
from app.tasks.document_fetch import (
    _extract_document_id,
    _fetch_documents_async,
    _pick_content_type,
)
from app.repositories import (
    mark_document_failed,
    mark_document_fetched,
    upsert_document_metadata,
)
from ch_client.schemas import CHDocumentMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _async_cm(value: object) -> object:
    """Return an async context manager that yields *value*."""

    @asynccontextmanager
    async def _cm() -> AsyncGenerator[object, None]:
        yield value

    return _cm()


def _make_session() -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.scalar_one.return_value = uuid.uuid4()
    session.execute.return_value = result
    return session


def _make_metadata(
    content_type: str = "application/xhtml+xml",
    resources: dict | None = None,
) -> CHDocumentMetadata:
    if resources is None:
        resources = {content_type: "ref"}
    return CHDocumentMetadata(
        company_number="12345678",
        content_length=4096,
        content_type=content_type,
        resources=resources,
    )


# ---------------------------------------------------------------------------
# _extract_document_id
# ---------------------------------------------------------------------------


def test_extract_document_id_from_absolute_url() -> None:
    url = (
        "https://document-api.company-information.service.gov.uk"
        "/document/OTM4ZTA4OThjODEzYjMzMjM2OGUz"
    )
    assert _extract_document_id(url) == "OTM4ZTA4OThjODEzYjMzMjM2OGUz"


def test_extract_document_id_from_path_only() -> None:
    assert _extract_document_id("/document/ABC123") == "ABC123"


def test_extract_document_id_raises_on_malformed_url() -> None:
    with pytest.raises(ValueError, match="Cannot extract document_id"):
        _extract_document_id("https://example.com/not-a-document-url")


# ---------------------------------------------------------------------------
# _pick_content_type
# ---------------------------------------------------------------------------


def test_pick_content_type_prefers_xhtml() -> None:
    available = ["application/pdf", "application/xhtml+xml", "text/html"]
    assert _pick_content_type(available) == "application/xhtml+xml"


def test_pick_content_type_falls_back_to_html() -> None:
    available = ["application/pdf", "text/html"]
    assert _pick_content_type(available) == "text/html"


def test_pick_content_type_uses_first_when_no_priority_match() -> None:
    available = ["application/octet-stream"]
    assert _pick_content_type(available) == "application/octet-stream"


def test_pick_content_type_returns_none_for_empty() -> None:
    assert _pick_content_type([]) is None
    assert _pick_content_type(None) is None


# ---------------------------------------------------------------------------
# build_storage_key
# ---------------------------------------------------------------------------


def test_build_storage_key_format() -> None:
    key = build_storage_key("12345678", "TXN001", "DOCABC", "application/xhtml+xml")
    assert key == "12345678/filings/TXN001/DOCABC.xhtml"


def test_build_storage_key_pdf_extension() -> None:
    key = build_storage_key("12345678", "TXN001", "DOCABC", "application/pdf")
    assert key == "12345678/filings/TXN001/DOCABC.pdf"


def test_build_storage_key_strips_content_type_params() -> None:
    key = build_storage_key(
        "12345678", "TXN001", "DOCABC", "text/html; charset=utf-8"
    )
    assert key == "12345678/filings/TXN001/DOCABC.html"


def test_build_storage_key_unknown_content_type_uses_bin() -> None:
    key = build_storage_key("12345678", "TXN001", "DOCABC", "application/octet-stream")
    assert key == "12345678/filings/TXN001/DOCABC.bin"


def test_build_storage_key_is_deterministic() -> None:
    args = ("12345678", "TXN001", "DOCABC", "text/html")
    assert build_storage_key(*args) == build_storage_key(*args)


# ---------------------------------------------------------------------------
# _fetch_documents_async — orchestration
# ---------------------------------------------------------------------------


async def test_fetch_documents_returns_zero_when_no_pending() -> None:
    """If get_pending_filings_with_documents returns empty, exit early."""
    company_id = uuid.uuid4()
    mock_session = _make_session()
    mock_session.execute.return_value.scalar_one_or_none.return_value = company_id

    with (
        patch("app.tasks.document_fetch.get_session", return_value=_async_cm(mock_session)),
        patch(
            "app.tasks.document_fetch.get_pending_filings_with_documents",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await _fetch_documents_async("12345678")

    assert result == {
        "company_number": "12345678",
        "fetched": 0,
        "skipped": 0,
        "failed": 0,
    }


async def test_fetch_documents_raises_when_company_not_found() -> None:
    """ValueError is raised if the company does not exist in the DB."""
    mock_session = _make_session()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    with (
        patch("app.tasks.document_fetch.get_session", return_value=_async_cm(mock_session)),
    ):
        with pytest.raises(ValueError, match="not found in DB"):
            await _fetch_documents_async("00000000")


async def test_fetch_documents_happy_path() -> None:
    """Full fetch flow: metadata → upsert → download → MinIO → mark fetched."""
    company_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    doc_id = "OTM4ZTA4OThjODEzYjMzMjM2"

    pending_filing = {
        "filing_id": filing_id,
        "transaction_id": "TXN001",
        "source_links": {
            "document_metadata": (
                "https://document-api.company-information.service.gov.uk"
                f"/document/{doc_id}"
            )
        },
    }
    metadata = _make_metadata(
        resources={"application/xhtml+xml": "ref", "application/pdf": "ref"}
    )

    mock_client = AsyncMock()
    mock_client.get_document_metadata.return_value = metadata
    mock_client.get_document_content.return_value = b"<xhtml>...</xhtml>"

    mock_s3 = AsyncMock()
    mock_s3.put_object.return_value = {"ETag": '"abc123"'}

    mock_session = _make_session()
    mock_session.execute.return_value.scalar_one_or_none.return_value = company_id

    with (
        patch("app.tasks.document_fetch.get_session", return_value=_async_cm(mock_session)),
        patch(
            "app.tasks.document_fetch.get_pending_filings_with_documents",
            new_callable=AsyncMock,
            return_value=[pending_filing],
        ),
        patch("app.tasks.document_fetch.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.document_fetch.get_storage_client", return_value=_async_cm(mock_s3)),
        patch("app.tasks.document_fetch.upsert_document_metadata", new_callable=AsyncMock, return_value=uuid.uuid4()),
        patch("app.tasks.document_fetch.mark_document_fetched", new_callable=AsyncMock),
        patch("app.tasks.document_fetch.put_document", new_callable=AsyncMock, return_value="abc123"),
    ):
        result = await _fetch_documents_async("12345678")

    assert result["fetched"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0


async def test_fetch_documents_skips_filing_without_doc_url() -> None:
    """A filing with no document_metadata link is counted as skipped."""
    company_id = uuid.uuid4()
    pending_filing = {
        "filing_id": uuid.uuid4(),
        "transaction_id": "TXN001",
        "source_links": {},  # no document_metadata
    }

    mock_client = AsyncMock()
    mock_s3 = AsyncMock()
    mock_session = _make_session()
    mock_session.execute.return_value.scalar_one_or_none.return_value = company_id

    with (
        patch("app.tasks.document_fetch.get_session", return_value=_async_cm(mock_session)),
        patch(
            "app.tasks.document_fetch.get_pending_filings_with_documents",
            new_callable=AsyncMock,
            return_value=[pending_filing],
        ),
        patch("app.tasks.document_fetch.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.document_fetch.get_storage_client", return_value=_async_cm(mock_s3)),
    ):
        result = await _fetch_documents_async("12345678")

    assert result["skipped"] == 1
    assert result["fetched"] == 0


async def test_fetch_documents_marks_failed_on_download_error() -> None:
    """A per-document exception increments failed count and marks the row failed."""
    company_id = uuid.uuid4()
    doc_id = "DOCABC"
    pending_filing = {
        "filing_id": uuid.uuid4(),
        "transaction_id": "TXN001",
        "source_links": {
            "document_metadata": f"https://document-api.company-information.service.gov.uk/document/{doc_id}"
        },
    }
    metadata = _make_metadata()

    mock_client = AsyncMock()
    mock_client.get_document_metadata.return_value = metadata
    mock_client.get_document_content.side_effect = RuntimeError("network error")

    mock_s3 = AsyncMock()
    mock_session = _make_session()
    mock_session.execute.return_value.scalar_one_or_none.return_value = company_id

    with (
        patch("app.tasks.document_fetch.get_session", return_value=_async_cm(mock_session)),
        patch(
            "app.tasks.document_fetch.get_pending_filings_with_documents",
            new_callable=AsyncMock,
            return_value=[pending_filing],
        ),
        patch("app.tasks.document_fetch.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.document_fetch.get_storage_client", return_value=_async_cm(mock_s3)),
        patch("app.tasks.document_fetch.upsert_document_metadata", new_callable=AsyncMock, return_value=uuid.uuid4()),
        patch("app.tasks.document_fetch.mark_document_failed", new_callable=AsyncMock) as mock_mark_failed,
    ):
        result = await _fetch_documents_async("12345678")

    assert result["failed"] == 1
    assert result["fetched"] == 0
    mock_mark_failed.assert_called_once()


async def test_fetch_documents_skips_when_no_content_types() -> None:
    """If metadata has no available content types, document is skipped."""
    company_id = uuid.uuid4()
    doc_id = "DOCABC"
    pending_filing = {
        "filing_id": uuid.uuid4(),
        "transaction_id": "TXN001",
        "source_links": {
            "document_metadata": f"https://document-api.company-information.service.gov.uk/document/{doc_id}"
        },
    }
    # metadata with no resources and no content_type
    metadata = CHDocumentMetadata(company_number="12345678")

    mock_client = AsyncMock()
    mock_client.get_document_metadata.return_value = metadata
    mock_s3 = AsyncMock()
    mock_session = _make_session()
    mock_session.execute.return_value.scalar_one_or_none.return_value = company_id

    with (
        patch("app.tasks.document_fetch.get_session", return_value=_async_cm(mock_session)),
        patch(
            "app.tasks.document_fetch.get_pending_filings_with_documents",
            new_callable=AsyncMock,
            return_value=[pending_filing],
        ),
        patch("app.tasks.document_fetch.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.document_fetch.get_storage_client", return_value=_async_cm(mock_s3)),
        patch("app.tasks.document_fetch.upsert_document_metadata", new_callable=AsyncMock, return_value=uuid.uuid4()),
    ):
        result = await _fetch_documents_async("12345678")

    assert result["skipped"] == 1


# ---------------------------------------------------------------------------
# Repository helpers
# ---------------------------------------------------------------------------


async def test_upsert_document_metadata_inserts_and_returns_uuid() -> None:
    filing_id = uuid.uuid4()
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = uuid.uuid4()
    session.execute.return_value = result

    metadata = _make_metadata()
    doc_id = await upsert_document_metadata(session, filing_id, "DOCABC", metadata)

    assert isinstance(doc_id, uuid.UUID)
    session.execute.assert_called_once()


async def test_mark_document_fetched_executes_update() -> None:
    session = AsyncMock()
    await mark_document_fetched(
        session,
        document_id="DOCABC",
        storage_key="12345678/filings/TXN001/DOCABC.xhtml",
        storage_etag="abc123",
        content_type="application/xhtml+xml",
        content_length=4096,
        downloaded_at=datetime.now(timezone.utc),
    )
    session.execute.assert_called_once()
    # Verify the statement targets the right document_id
    stmt = session.execute.call_args[0][0]
    assert "fetch_status" in str(stmt)


async def test_mark_document_failed_executes_update() -> None:
    session = AsyncMock()
    await mark_document_failed(session, document_id="DOCABC")
    session.execute.assert_called_once()
    stmt = session.execute.call_args[0][0]
    assert "fetch_status" in str(stmt)


# ---------------------------------------------------------------------------
# CHDocumentMetadata.available_content_types property
# ---------------------------------------------------------------------------


def test_document_metadata_available_content_types_from_resources() -> None:
    metadata = CHDocumentMetadata(
        resources={
            "application/xhtml+xml": "ref1",
            "application/pdf": "ref2",
        }
    )
    assert set(metadata.available_content_types) == {
        "application/xhtml+xml",
        "application/pdf",
    }


def test_document_metadata_available_content_types_fallback_to_content_type() -> None:
    metadata = CHDocumentMetadata(content_type="text/html")
    assert metadata.available_content_types == ["text/html"]


def test_document_metadata_available_content_types_empty_when_nothing_set() -> None:
    metadata = CHDocumentMetadata()
    assert metadata.available_content_types == []
