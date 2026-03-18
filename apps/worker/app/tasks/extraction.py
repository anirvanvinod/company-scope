"""
Financial fact extraction Celery tasks — Phase 5B.

extract_facts(company_number)
    Picks up all filing_documents that have been classified
    (parse_status='classified', document_format in ixbrl/xbrl/html) and
    extracts canonical financial facts from each.

    For each document it:
      1. Downloads raw bytes from MinIO object storage.
      2. Dispatches to the appropriate extractor (ixbrl_extractor or
         html_extractor) based on document_format.
      3. Filters extracted facts to those with a canonical_name and a
         non-None fact_value.
      4. Determines the financial period (from document or filing action_date
         fallback).
      5. Upserts a financial_periods row.
      6. Upserts financial_facts rows (one per canonical fact).
      7. Updates extraction_runs with final status and aggregate confidence.
      8. Advances parse_status to 'parsed' (success) or 'failed' (error).

Idempotency:
    Financial period upsert is ON CONFLICT DO UPDATE — re-running the
    task overwrites with the most recent extraction.
    parse_status='parsed' documents are excluded from the selection query,
    so successfully extracted documents are not re-processed.
    'failed' documents revert to 'classified' via the Phase 5A task re-run,
    then Phase 5B re-attempts extraction.

Non-retryable: ValueError (company not in DB or missing storage key).
Retryable: transient DB errors, MinIO errors, unexpected exceptions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from app.adapters.object_store import get_document, get_storage_client
from app.db import get_session
from app.main import celery_app
from app.parsers.classifier import PARSER_VERSION
from app.parsers.html_extractor import extract_html
from app.parsers.ixbrl_extractor import extract_ixbrl
from app.parsers.models import ExtractionResult
from app.repositories import (
    create_extraction_run,
    finish_extraction_run,
    get_classified_documents_for_extraction,
    update_document_parse_status,
    upsert_financial_facts,
    upsert_financial_period,
)
from app.config import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _extract_facts_async(company_number: str) -> dict[str, Any]:
    """
    Extract financial facts for all classified documents of a company.
    """
    extracted = 0
    no_facts = 0
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
            "Run refresh_company first."
        )

    # --- find classified documents ---
    async with get_session() as session:
        documents = await get_classified_documents_for_extraction(session, company_id)

    if not documents:
        log.info("No classified documents ready for extraction for %s", company_number)
        return {
            "company_number": company_number,
            "extracted": 0,
            "no_facts": 0,
            "failed": 0,
        }

    log.info(
        "Found %d classified document(s) for extraction for %s",
        len(documents),
        company_number,
    )

    _enqueue_analysis = False

    async with get_storage_client() as s3:
        for doc in documents:
            filing_document_id: uuid.UUID = doc["filing_document_id"]
            document_id: str = doc["document_id"]
            document_format: str = doc["document_format"]
            storage_key: str | None = doc["storage_key"]
            filing_id: uuid.UUID = doc["filing_id"]
            action_date: date | None = doc["action_date"]

            if not storage_key:
                log.warning(
                    "Document %s has no storage_key; skipping", document_id
                )
                failed += 1
                continue

            run_id: uuid.UUID | None = None
            try:
                # 1. Download raw bytes from MinIO
                content = await get_document(
                    s3, settings.minio_bucket_documents, storage_key
                )

                # 2. Dispatch to appropriate extractor
                result_obj: ExtractionResult = _dispatch_extractor(
                    document_format, content
                )

                if result_obj.errors:
                    log.warning(
                        "Extractor errors for document %s: %s",
                        document_id,
                        result_obj.errors,
                    )

                # 3. Create extraction run (audit; committed immediately)
                run_id = await create_extraction_run(
                    filing_id=filing_id,
                    filing_document_id=filing_document_id,
                    document_format=document_format,
                    parser_version=PARSER_VERSION,
                )

                # 4. Filter to persistable facts
                persistable = [
                    f
                    for f in result_obj.facts
                    if f.canonical_name is not None and f.fact_value is not None
                ]

                # Only persist non-comparative facts for the primary period.
                # Comparative facts (prior-year) are excluded from Phase 5B.
                primary_facts = [f for f in persistable if not f.is_comparative]

                # 5. Determine the financial period
                period_end = result_obj.period_end or action_date
                if period_end is None:
                    log.warning(
                        "No period_end for document %s; no financial period created",
                        document_id,
                    )
                    await finish_extraction_run(
                        run_id,
                        status="completed",
                        confidence=Decimal("0"),
                        warnings=["No period_end detected — no period created"],
                    )
                    async with get_session() as session:
                        await update_document_parse_status(
                            session,
                            document_id=document_id,
                            parse_status="parsed",
                        )
                        await session.commit()
                    no_facts += 1
                    continue

                # Resolve company_id into a UUID for the source_document lookup
                async with get_session() as session:
                    fd_result = await session.execute(
                        sa.text(
                            "SELECT id FROM filing_documents WHERE document_id = :did"
                        ),
                        {"did": document_id},
                    )
                    source_doc_uuid: uuid.UUID | None = (
                        fd_result.scalar_one_or_none()
                    )

                if source_doc_uuid is None:
                    # Fallback: use filing_document_id we already have
                    source_doc_uuid = filing_document_id

                # 6. Upsert financial_period
                async with get_session() as session:
                    period_id = await upsert_financial_period(
                        session,
                        company_id=company_id,
                        filing_id=filing_id,
                        source_document_id=source_doc_uuid,
                        period_start=result_obj.period_start,
                        period_end=period_end,
                        accounts_type=result_obj.accounts_type,
                        currency_code=result_obj.currency_code,
                        extraction_confidence=result_obj.run_confidence,
                    )
                    # 7. Upsert financial_facts
                    facts_count = await upsert_financial_facts(
                        session,
                        period_id=period_id,
                        company_id=company_id,
                        source_document_id=source_doc_uuid,
                        source_filing_id=filing_id,
                        facts=primary_facts,
                    )
                    await session.commit()

                log.info(
                    "Persisted %d canonical fact(s) from document %s "
                    "(format=%s, period_end=%s)",
                    facts_count,
                    document_id,
                    document_format,
                    period_end,
                )

                # 8. Finish extraction run
                await finish_extraction_run(
                    run_id,
                    status="completed",
                    confidence=result_obj.run_confidence,
                    warnings=result_obj.warnings if result_obj.warnings else None,
                    errors=(
                        {"parse_errors": result_obj.errors}
                        if result_obj.errors
                        else None
                    ),
                )

                # 9. Advance parse_status
                async with get_session() as session:
                    await update_document_parse_status(
                        session,
                        document_id=document_id,
                        parse_status="parsed",
                    )
                    await session.commit()

                if facts_count == 0:
                    no_facts += 1
                else:
                    extracted += 1
                    _enqueue_analysis = True

            except Exception as exc:
                log.exception(
                    "Extraction failed for document %s: %s", document_id, exc
                )
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
                try:
                    async with get_session() as session:
                        await update_document_parse_status(
                            session,
                            document_id=document_id,
                            parse_status="failed",
                        )
                        await session.commit()
                except Exception:
                    log.exception(
                        "Could not mark document %s parse-failed", document_id
                    )
                failed += 1

    # Enqueue analysis task if at least one document was successfully extracted.
    if _enqueue_analysis:
        from app.tasks.analysis import compute_analysis  # deferred to avoid circular import
        compute_analysis.delay(company_number)
        log.info("Enqueued compute_analysis for %s", company_number)

    return {
        "company_number": company_number,
        "extracted": extracted,
        "no_facts": no_facts,
        "failed": failed,
    }


def _dispatch_extractor(document_format: str, content: bytes) -> ExtractionResult:
    """Dispatch to the correct extractor based on document_format."""
    if document_format in ("ixbrl", "xbrl"):
        return extract_ixbrl(content)
    if document_format == "html":
        return extract_html(content)
    # Should not reach here — selection query only returns supported formats.
    from app.parsers.models import ExtractionResult
    from decimal import Decimal

    return ExtractionResult(
        facts=[],
        period_start=None,
        period_end=None,
        accounts_type=None,
        currency_code="GBP",
        run_confidence=Decimal("0"),
        warnings=[],
        errors=[f"Unsupported document_format: {document_format!r}"],
        extraction_method=document_format,
    )


# ---------------------------------------------------------------------------
# Celery task definition
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="extraction.extract_facts",
    queue="document_parse",
    max_retries=3,
    default_retry_delay=120,
)
def extract_facts(self: Any, company_number: str) -> dict[str, Any]:
    """
    Extract canonical financial facts from all classified documents for a company.

    Enqueue after parse_documents to perform financial fact extraction
    on all iXBRL and HTML classified documents.

    Non-retryable: ValueError (company not in DB, missing storage key).
    Retryable: transient storage / DB errors.
    """
    try:
        return asyncio.run(_extract_facts_async(company_number))
    except ValueError:
        raise  # non-retryable
    except Exception as exc:
        log.exception("extract_facts failed for %s: %s", company_number, exc)
        raise self.retry(exc=exc)
