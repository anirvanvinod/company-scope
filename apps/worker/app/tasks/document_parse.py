"""
Document parse Celery tasks — Phase 5A: classification only.

parse_documents(company_number)
    Identifies all filing_documents that have been fetched but not yet
    classified (fetch_status='fetched', parse_status='pending' or 'failed').
    For each document it:
      1. Classifies the document format from stored content_type metadata.
      2. Creates an extraction_runs row (status='running').
      3. Writes document_format back to the filing_documents row.
      4. Advances parse_status:
           - 'classified'  — supported format; ready for Phase 5B extraction.
           - 'unsupported' — format not extractable; terminal state.
      5. Finishes the extraction_runs row (status='completed'|'unsupported').

Phase 5B will extend this pipeline to read the document bytes from MinIO
and perform structured fact extraction for 'classified' documents.

Idempotency:
    - Documents with parse_status='classified', 'parsed', or 'unsupported'
      are excluded from the selection query.
    - 'failed' documents are retried on the next run.
    - Classification is deterministic from content_type, so re-running a
      failed document always produces the same document_format.
    - Each run creates a new extraction_runs row, preserving audit history.

Non-retryable: ValueError (company not in DB).
Retryable: transient DB errors, unexpected exceptions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import sqlalchemy as sa

from app.db import get_session
from app.main import celery_app
from app.parsers.classifier import PARSER_VERSION, classify_document
from app.repositories import (
    create_extraction_run,
    finish_extraction_run,
    get_documents_ready_for_parse,
    update_document_parse_status,
)

log = logging.getLogger(__name__)

# Formats that the extraction pipeline supports.  Documents classified into
# any of these formats will be advanced to 'classified' and picked up by
# Phase 5B.  All other formats are marked 'unsupported'.
_EXTRACTABLE_FORMATS = frozenset({"ixbrl", "xbrl", "html"})


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _parse_documents_async(company_number: str) -> dict[str, Any]:
    """
    Classify all pending fetchable documents for a company.

    Opens a short-lived session to resolve the company_id and retrieve
    pending documents, then processes each document with independent
    sessions to keep transactions small and audit records durable.
    """
    classified = 0
    unsupported = 0
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

    # --- find documents ready for classification ---
    async with get_session() as session:
        documents = await get_documents_ready_for_parse(session, company_id)

    if not documents:
        log.info("No documents pending classification for %s", company_number)
        return {
            "company_number": company_number,
            "classified": 0,
            "unsupported": 0,
            "failed": 0,
        }

    log.info(
        "Found %d document(s) pending classification for %s",
        len(documents),
        company_number,
    )

    for doc in documents:
        filing_document_id: uuid.UUID = doc["filing_document_id"]
        document_id: str = doc["document_id"]
        content_type: str | None = doc["content_type"]
        filing_id: uuid.UUID = doc["filing_id"]

        run_id: uuid.UUID | None = None
        try:
            # 1. Classify format from stored content_type metadata
            fmt = classify_document(content_type)

            # 2. Create extraction_run (committed immediately in own session)
            run_id = await create_extraction_run(
                filing_id=filing_id,
                filing_document_id=filing_document_id,
                document_format=fmt,
                parser_version=PARSER_VERSION,
            )

            # 3. Persist format and advance parse_status
            if fmt in _EXTRACTABLE_FORMATS:
                async with get_session() as session:
                    await update_document_parse_status(
                        session,
                        document_id=document_id,
                        parse_status="classified",
                        document_format=fmt,
                    )
                    await session.commit()
                await finish_extraction_run(run_id, status="completed")
                log.info(
                    "Classified document %s as %s (filing_document_id=%s)",
                    document_id,
                    fmt,
                    filing_document_id,
                )
                classified += 1

            else:
                # 'pdf' and 'unsupported' are not extractable in Phase MVP
                async with get_session() as session:
                    await update_document_parse_status(
                        session,
                        document_id=document_id,
                        parse_status="unsupported",
                        document_format=fmt,
                    )
                    await session.commit()
                await finish_extraction_run(run_id, status="unsupported")
                log.info(
                    "Document %s marked unsupported (format=%s, filing_document_id=%s)",
                    document_id,
                    fmt,
                    filing_document_id,
                )
                unsupported += 1

        except Exception as exc:
            log.exception(
                "Failed to classify document %s (filing_document_id=%s): %s",
                document_id,
                filing_document_id,
                exc,
            )
            # Finish the run as failed if it was created
            if run_id is not None:
                try:
                    await finish_extraction_run(
                        run_id,
                        status="failed",
                        errors={"exception": str(exc)[:500]},
                    )
                except Exception:
                    log.exception(
                        "Could not finish extraction_run %s as failed", run_id
                    )
            # Mark the document as failed so it is retried on the next run
            try:
                async with get_session() as session:
                    await update_document_parse_status(
                        session, document_id=document_id, parse_status="failed"
                    )
                    await session.commit()
            except Exception:
                log.exception(
                    "Could not mark document %s as parse-failed", document_id
                )
            failed += 1

    return {
        "company_number": company_number,
        "classified": classified,
        "unsupported": unsupported,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Celery task definition
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="document_parse.parse_documents",
    queue="document_parse",
    max_retries=3,
    default_retry_delay=60,
)
def parse_documents(self: Any, company_number: str) -> dict[str, Any]:
    """
    Classify all pending fetched documents for a company.

    Enqueue after fetch_documents to advance documents from 'fetched'
    through format classification so Phase 5B extraction can begin.

    Non-retryable: ValueError (company not in DB).
    Retryable: transient DB errors and unexpected exceptions.
    """
    try:
        return asyncio.run(_parse_documents_async(company_number))
    except ValueError:
        raise  # non-retryable — company missing from DB
    except Exception as exc:
        log.exception("parse_documents failed for %s: %s", company_number, exc)
        raise self.retry(exc=exc)
