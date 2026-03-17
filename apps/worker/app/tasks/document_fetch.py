"""
Document fetch Celery tasks.

fetch_documents(company_number)
    Identifies all account-category filings for the company that have a
    document_metadata link and have not yet been fetched.  For each such
    filing it:
      1. Fetches metadata from the CH Document API.
      2. Upserts a filing_documents row (fetch_status='pending').
      3. Downloads the document content in the best available format.
      4. Stores the raw bytes in MinIO under a deterministic key.
      5. Updates the filing_documents row (fetch_status='fetched').

    Per-document errors are caught, logged, and recorded as
    fetch_status='failed' so the batch continues.  The next run of
    fetch_documents will retry failed documents.

    CH auth errors and 404s are re-raised immediately — they are not
    retriable at the Celery level.

Idempotency:
    Documents with fetch_status='fetched' are excluded from the pending
    query, so re-running the task is safe.  MinIO put_object is also
    idempotent (same key, same content).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa

from ch_client.exceptions import CHAuthError, CHNotFoundError
from app.adapters.companies_house import create_ch_client
from app.adapters.object_store import (
    CONTENT_TYPE_PRIORITY,
    build_storage_key,
    get_storage_client,
    put_document,
)
from app.config import settings
from app.db import get_session
from app.main import celery_app
from app.repositories import (
    get_pending_filings_with_documents,
    mark_document_failed,
    mark_document_fetched,
    upsert_document_metadata,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_document_id(document_metadata_url: str) -> str:
    """
    Extract the document_id from a CH Document API metadata URL.

    Handles both absolute and path-only forms:
      "https://document-api.company-information.service.gov.uk/document/OTM4..."
      "/document/OTM4..."

    Returns the document_id string (the path segment after "/document/").
    Raises ValueError if the URL cannot be parsed.
    """
    path = urlparse(document_metadata_url).path
    parts = [p for p in path.split("/") if p]
    try:
        doc_idx = parts.index("document")
        return parts[doc_idx + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError(
            f"Cannot extract document_id from URL: {document_metadata_url!r}"
        ) from exc


def _pick_content_type(available: list[str] | None) -> str | None:
    """
    Return the highest-priority downloadable content type.

    Prefers structured formats (iXBRL/HTML/XML) over PDF because the parser
    phase can only extract financial facts from structured content.
    Returns None if *available* is empty.
    """
    if not available:
        return None
    for ct in CONTENT_TYPE_PRIORITY:
        if ct in available:
            return ct
    # Fall back to first available if none match the priority list
    return available[0]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _fetch_documents_async(company_number: str) -> dict[str, Any]:
    """
    Fetch all pending fetchable account documents for a company.

    Opens a short-lived session to identify pending filings, then processes
    each document with independent sessions to keep transactions small.
    """
    fetched = 0
    skipped = 0
    failed = 0

    # --- resolve company_id ---
    async with get_session() as session:
        result = await session.execute(
            sa.text("SELECT id FROM companies WHERE company_number = :cn"),
            {"cn": company_number},
        )
        company_id: uuid.UUID | None = result.scalar_one_or_none()

    if company_id is None:
        raise ValueError(
            f"Company {company_number!r} not found in DB. "
            "Run refresh_company first to create the canonical record."
        )

    # --- find pending filings ---
    async with get_session() as session:
        filings = await get_pending_filings_with_documents(session, company_id)

    if not filings:
        log.info("No pending fetchable documents for %s", company_number)
        return {
            "company_number": company_number,
            "fetched": 0,
            "skipped": 0,
            "failed": 0,
        }

    log.info(
        "Found %d pending document(s) for %s", len(filings), company_number
    )

    async with create_ch_client() as client:
        async with get_storage_client() as s3:
            for filing in filings:
                filing_id: uuid.UUID = filing["filing_id"]
                transaction_id: str = filing["transaction_id"]
                source_links: dict[str, Any] = filing["source_links"] or {}

                doc_url: str | None = source_links.get("document_metadata")
                if not doc_url:
                    log.debug(
                        "Filing %s has no document_metadata link, skipping",
                        filing_id,
                    )
                    skipped += 1
                    continue

                try:
                    document_id = _extract_document_id(doc_url)
                except ValueError as exc:
                    log.warning(
                        "Cannot parse document_id for filing %s: %s", filing_id, exc
                    )
                    skipped += 1
                    continue

                try:
                    # 1. Fetch document metadata from CH Document API
                    metadata = await client.get_document_metadata(document_id)

                    # 2. Upsert filing_documents row with metadata
                    async with get_session() as session:
                        await upsert_document_metadata(
                            session, filing_id, document_id, metadata
                        )
                        await session.commit()

                    # 3. Determine best content type to download
                    content_type = _pick_content_type(
                        metadata.available_content_types
                    )
                    if content_type is None:
                        log.warning(
                            "No available content types for document %s; skipping",
                            document_id,
                        )
                        skipped += 1
                        continue

                    # 4. Download content from CH Document API
                    content = await client.get_document_content(
                        document_id, content_type
                    )

                    # 5. Store in MinIO under deterministic key
                    storage_key = build_storage_key(
                        company_number, transaction_id, document_id, content_type
                    )
                    etag = await put_document(
                        s3,
                        settings.minio_bucket_documents,
                        storage_key,
                        content,
                        content_type,
                    )
                    downloaded_at = _now()

                    # 6. Mark as fetched in DB
                    async with get_session() as session:
                        await mark_document_fetched(
                            session,
                            document_id=document_id,
                            storage_key=storage_key,
                            storage_etag=etag,
                            content_type=content_type,
                            content_length=len(content),
                            downloaded_at=downloaded_at,
                        )
                        await session.commit()

                    log.info(
                        "Fetched document %s → %s (%d bytes, etag=%s)",
                        document_id,
                        storage_key,
                        len(content),
                        etag,
                    )
                    fetched += 1

                except (CHAuthError, CHNotFoundError):
                    # Non-retryable upstream errors: surface immediately to
                    # the Celery task wrapper which will not retry them.
                    raise

                except Exception as exc:
                    log.exception(
                        "Failed to fetch document %s for filing %s: %s",
                        document_id,
                        filing_id,
                        exc,
                    )
                    # Mark as failed but continue processing remaining documents
                    try:
                        async with get_session() as session:
                            await mark_document_failed(session, document_id)
                            await session.commit()
                    except Exception:
                        log.exception(
                            "Could not mark document %s as failed", document_id
                        )
                    failed += 1

    return {
        "company_number": company_number,
        "fetched": fetched,
        "skipped": skipped,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Celery task definition
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="document_fetch.fetch_documents",
    queue="document_fetch",
    max_retries=3,
    default_retry_delay=120,
)
def fetch_documents(self: Any, company_number: str) -> dict[str, Any]:
    """
    Fetch and store all pending account documents for a company.

    Enqueue after refresh_company to populate filing_documents with raw
    content that the parser phase can process.

    Non-retryable: CHAuthError (bad API key), CHNotFoundError (404).
    Retryable: transient network errors, rate limits, 5xx responses.
    """
    try:
        return asyncio.run(_fetch_documents_async(company_number))
    except (CHAuthError, CHNotFoundError):
        raise  # non-retryable
    except Exception as exc:
        log.exception(
            "fetch_documents failed for %s: %s", company_number, exc
        )
        raise self.retry(exc=exc)
