"""
Snapshot build Celery task — Phase 6B.

build_snapshot(company_number)
    Builds and persists a full company snapshot (read-model) including the
    AI-generated or template-based narrative summary.

    Triggered automatically after compute_analysis completes.
    May also be called independently to rebuild the snapshot after a
    methodology version bump or model change.

Idempotency:
    upsert_company_snapshot() retires the previous is_current snapshot and
    inserts a fresh row.  Re-running always produces the latest snapshot.

Non-retryable: ValueError (company not in DB or no primary period).
Retryable: DB errors, transient AI endpoint failures (already handled
    inside snapshot_builder via template fallback).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.analytics.metrics import METHODOLOGY_VERSION
from app.analytics.snapshot_builder import build_company_snapshot
from app.db import get_session
from app.main import celery_app
from app.parsers.classifier import PARSER_VERSION
from app.repositories import upsert_company_snapshot

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _build_snapshot_async(company_number: str) -> dict[str, Any]:
    async with get_session() as session:
        company_id, payload = await build_company_snapshot(company_number, session)

        await upsert_company_snapshot(
            session,
            company_id=company_id,
            snapshot_payload=payload.model_dump(mode="json"),
            methodology_version=METHODOLOGY_VERSION,
            parser_version=PARSER_VERSION,
        )
        await session.commit()

    log.info(
        "Snapshot persisted for %s (source=%s)",
        company_number,
        payload.summary_source,
    )
    return {
        "company_number": company_number,
        "status": "ok",
        "summary_source": payload.summary_source,
        "methodology_version": METHODOLOGY_VERSION,
    }


# ---------------------------------------------------------------------------
# Celery task definition
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="snapshot.build_snapshot",
    queue="rebuild_snapshots",
    max_retries=3,
    default_retry_delay=60,
)
def build_snapshot(self: Any, company_number: str) -> dict[str, Any]:
    """
    Build and persist a company snapshot.

    Non-retryable: ValueError (company or period not found).
    Retryable: DB errors, unexpected exceptions.
    """
    try:
        return asyncio.run(_build_snapshot_async(company_number))
    except ValueError:
        raise  # non-retryable
    except Exception as exc:
        log.exception("build_snapshot failed for %s: %s", company_number, exc)
        raise self.retry(exc=exc)
