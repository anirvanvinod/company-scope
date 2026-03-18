"""
Ingestion repository — upsert functions for the five canonical entity types.

All functions accept an open AsyncSession and perform one or more
INSERT ... ON CONFLICT DO UPDATE statements.  None of them commit; callers
are responsible for committing (or rolling back) the transaction.

Table objects are defined locally (not imported from the API's ORM models)
because the worker and API share the 'app' top-level package name and cannot
safely import from each other.  The Table definitions here mirror the ORM
models and migration DDL exactly — the two must be kept in sync.

CH adapter schema classes are imported from the shared ch_client package.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import (
    ARRAY as PgArray,
    JSONB,
    UUID as PgUUID,
    insert as pg_insert,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ch_client.schemas import (
    CHChargeItem,
    CHCompanyProfile,
    CHDocumentMetadata,
    CHFilingHistoryItem,
    CHOfficerItem,
    CHPSCItem,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lightweight Table objects — mirrors the ORM models / migration DDL.
# Only columns actually written are declared; unlisted columns use DB defaults.
# ---------------------------------------------------------------------------

_meta = sa.MetaData()

_companies = sa.Table(
    "companies",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_number", sa.String(16)),
    sa.Column("company_name", sa.Text),
    sa.Column("jurisdiction", sa.String(64)),
    sa.Column("company_status", sa.String(64)),
    sa.Column("company_type", sa.String(64)),
    sa.Column("subtype", sa.String(64)),
    sa.Column("date_of_creation", sa.Date),
    sa.Column("cessation_date", sa.Date),
    sa.Column("has_insolvency_history", sa.Boolean),
    sa.Column("has_charges", sa.Boolean),
    sa.Column("accounts_next_due", sa.Date),
    sa.Column("accounts_overdue", sa.Boolean),
    sa.Column("confirmation_statement_next_due", sa.Date),
    sa.Column("confirmation_statement_overdue", sa.Boolean),
    sa.Column("registered_office_address", JSONB),
    sa.Column("sic_codes", PgArray(sa.Text)),
    sa.Column("source_etag", sa.Text),
    sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_filings = sa.Table(
    "filings",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("transaction_id", sa.String(64)),
    sa.Column("category", sa.String(64)),
    sa.Column("type", sa.String(32)),
    sa.Column("description", sa.Text),
    sa.Column("description_values", JSONB),
    sa.Column("action_date", sa.Date),
    sa.Column("date_filed", sa.Date),
    sa.Column("pages", sa.Integer),
    sa.Column("barcode", sa.Text),
    sa.Column("paper_filed", sa.Boolean),
    sa.Column("source_links", JSONB),
    sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_officers = sa.Table(
    "officers",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("name", sa.Text),
    sa.Column("officer_role", sa.String(64)),
    sa.Column("nationality", sa.Text),
    sa.Column("occupation", sa.Text),
    sa.Column("country_of_residence", sa.Text),
    sa.Column("date_of_birth_month", sa.SmallInteger),
    sa.Column("date_of_birth_year", sa.SmallInteger),
    sa.Column("raw_payload", JSONB),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_officer_appointments = sa.Table(
    "officer_appointments",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("officer_id", PgUUID(as_uuid=True)),
    sa.Column("role", sa.String(64)),
    sa.Column("appointed_on", sa.Date),
    sa.Column("resigned_on", sa.Date),
    sa.Column("is_pre_1992_appointment", sa.Boolean),
    sa.Column("address", JSONB),
    sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
    sa.Column("raw_payload", JSONB),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_psc_records = sa.Table(
    "psc_records",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("kind", sa.String(64)),
    sa.Column("name", sa.Text),
    sa.Column("notified_on", sa.Date),
    sa.Column("ceased_on", sa.Date),
    sa.Column("nationality", sa.Text),
    sa.Column("country_of_residence", sa.Text),
    sa.Column("date_of_birth_month", sa.SmallInteger),
    sa.Column("date_of_birth_year", sa.SmallInteger),
    sa.Column("natures_of_control", PgArray(sa.Text)),
    sa.Column("address", JSONB),
    sa.Column("raw_payload", JSONB),
    sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_charges = sa.Table(
    "charges",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("charge_id", sa.Text),
    sa.Column("status", sa.String(64)),
    sa.Column("resolved_on", sa.Date),
    sa.Column("delivered_on", sa.Date),
    sa.Column("created_on", sa.Date),
    sa.Column("persons_entitled", JSONB),
    sa.Column("particulars", JSONB),
    sa.Column("raw_payload", JSONB),
    sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_refresh_runs = sa.Table(
    "refresh_runs",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),  # nullable for full refreshes
    sa.Column("trigger_type", sa.String(32)),
    sa.Column("status", sa.String(16)),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.Column("error_summary", sa.Text),
)

_filing_documents = sa.Table(
    "filing_documents",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("filing_id", PgUUID(as_uuid=True)),
    sa.Column("document_id", sa.String(128)),
    sa.Column("original_filename", sa.Text),
    sa.Column("content_length", sa.BigInteger),
    sa.Column("content_type", sa.Text),
    sa.Column("available_content_types", PgArray(sa.Text)),
    sa.Column("storage_key", sa.Text),
    sa.Column("storage_etag", sa.Text),
    sa.Column("fetch_status", sa.String(32)),
    sa.Column("parse_status", sa.String(32)),
    sa.Column("document_format", sa.String(32)),  # added migration 0005
    sa.Column("downloaded_at", sa.DateTime(timezone=True)),
    sa.Column("metadata_payload", JSONB),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_extraction_runs = sa.Table(
    "extraction_runs",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("filing_id", PgUUID(as_uuid=True)),
    sa.Column("filing_document_id", PgUUID(as_uuid=True)),
    sa.Column("parser_version", sa.String(32)),
    sa.Column("document_format", sa.String(32)),  # added migration 0005
    sa.Column("status", sa.String(32)),
    sa.Column("confidence", sa.Numeric(5, 4)),     # aggregate run confidence
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
    sa.Column("warnings", JSONB),
    sa.Column("errors", JSONB),
)

_financial_periods = sa.Table(
    "financial_periods",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("filing_id", PgUUID(as_uuid=True)),
    sa.Column("period_start", sa.Date),
    sa.Column("period_end", sa.Date),
    sa.Column("period_length_days", sa.Integer),
    sa.Column("accounts_type", sa.String(64)),
    sa.Column("currency_code", sa.String(3)),
    sa.Column("is_restated", sa.Boolean),
    sa.Column("source_document_id", PgUUID(as_uuid=True)),
    sa.Column("extraction_confidence", sa.Numeric(5, 4)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_financial_facts = sa.Table(
    "financial_facts",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("financial_period_id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("fact_name", sa.String(128)),
    sa.Column("fact_value", sa.Numeric(20, 2)),   # nullable — never default to 0
    sa.Column("unit", sa.String(32)),
    sa.Column("raw_label", sa.Text),
    sa.Column("canonical_label", sa.String(128)),
    sa.Column("source_document_id", PgUUID(as_uuid=True)),
    sa.Column("source_filing_id", PgUUID(as_uuid=True)),
    sa.Column("extraction_method", sa.String(64)),
    sa.Column("extraction_confidence", sa.Numeric(5, 4)),
    sa.Column("is_derived", sa.Boolean),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_derived_metrics = sa.Table(
    "derived_metrics",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("financial_period_id", PgUUID(as_uuid=True)),
    sa.Column("prior_period_id", PgUUID(as_uuid=True)),    # nullable
    sa.Column("metric_key", sa.String(64)),
    sa.Column("metric_value", sa.Numeric(20, 6)),           # nullable
    sa.Column("unit", sa.String(32)),
    sa.Column("confidence", sa.Numeric(5, 4)),              # nullable
    sa.Column("confidence_band", sa.String(16)),
    sa.Column("warnings", JSONB),
    sa.Column("methodology_version", sa.String(16)),
    sa.Column("generated_at", sa.DateTime(timezone=True)),
)

_risk_signals = sa.Table(
    "risk_signals",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("signal_code", sa.String(64)),
    sa.Column("signal_name", sa.Text),
    sa.Column("category", sa.String(64)),
    sa.Column("severity", sa.String(16)),
    sa.Column("status", sa.String(16)),
    sa.Column("explanation", sa.Text),
    sa.Column("evidence", JSONB),
    sa.Column("methodology_version", sa.String(32)),
    sa.Column("first_detected_at", sa.DateTime(timezone=True)),
    sa.Column("last_confirmed_at", sa.DateTime(timezone=True)),
    sa.Column("resolved_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)

_company_snapshots = sa.Table(
    "company_snapshots",
    _meta,
    sa.Column("id", PgUUID(as_uuid=True)),
    sa.Column("company_id", PgUUID(as_uuid=True)),
    sa.Column("snapshot_version", sa.Integer),
    sa.Column("methodology_version", sa.String(32)),
    sa.Column("parser_version", sa.String(32)),
    sa.Column("freshness_status", sa.String(32)),
    sa.Column("snapshot_payload", JSONB),
    sa.Column("snapshot_generated_at", sa.DateTime(timezone=True)),
    sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
    sa.Column("is_current", sa.Boolean),
    sa.Column("created_at", sa.DateTime(timezone=True)),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _addr_dict(profile: CHCompanyProfile) -> dict[str, Any] | None:
    """Serialize CHAddress to a plain dict for JSONB storage."""
    if profile.registered_office_address is None:
        return None
    return profile.registered_office_address.model_dump(exclude_none=True)


# ---------------------------------------------------------------------------
# Upsert functions
# ---------------------------------------------------------------------------


async def upsert_company(
    session: AsyncSession, profile: CHCompanyProfile
) -> uuid.UUID:
    """
    Upsert a company profile row.

    Conflict key: company_number (unique).
    Always updates all mutable fields and source_last_checked_at.
    Returns the canonical company UUID (stable across upserts).
    """
    now = _now()
    accounts = profile.accounts
    cs = profile.confirmation_statement

    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "company_number": profile.company_number,
        "company_name": profile.company_name,
        "jurisdiction": profile.jurisdiction,
        "company_status": profile.company_status,
        "company_type": profile.type,
        "subtype": profile.subtype,
        "date_of_creation": profile.date_of_creation,
        "cessation_date": profile.date_of_cessation,
        "has_insolvency_history": profile.has_insolvency_history,
        "has_charges": profile.has_charges,
        "accounts_next_due": accounts.next_due if accounts else None,
        "accounts_overdue": accounts.overdue if accounts else None,
        "confirmation_statement_next_due": cs.next_due if cs else None,
        "confirmation_statement_overdue": cs.overdue if cs else None,
        "registered_office_address": _addr_dict(profile),
        "sic_codes": profile.sic_codes,
        "source_etag": profile.etag,
        "source_last_checked_at": now,
        "updated_at": now,
    }

    update_set = {k: v for k, v in values.items() if k != "id"}

    stmt = (
        pg_insert(_companies)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["company_number"],
            set_=update_set,
        )
        .returning(_companies.c.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def upsert_filings(
    session: AsyncSession,
    company_id: uuid.UUID,
    items: list[CHFilingHistoryItem],
) -> list[uuid.UUID]:
    """
    Upsert a batch of filing history items for a company.

    Conflict key: (company_id, transaction_id).
    Returns list of filing UUIDs in the same order as *items*.
    """
    if not items:
        return []

    now = _now()
    ids: list[uuid.UUID] = []

    for item in items:
        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "company_id": company_id,
            "transaction_id": item.transaction_id,
            "category": item.category,
            "type": item.type,
            "description": item.description,
            "description_values": item.description_values,
            "action_date": item.action_date,
            "date_filed": item.date,
            "pages": item.pages,
            "barcode": item.barcode,
            "paper_filed": item.paper_filed,
            "source_links": item.links,
            "source_last_checked_at": now,
            "updated_at": now,
        }
        update_set = {
            k: v
            for k, v in values.items()
            if k not in ("id", "company_id", "transaction_id")
        }
        stmt = (
            pg_insert(_filings)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["company_id", "transaction_id"],
                set_=update_set,
            )
            .returning(_filings.c.id)
        )
        result = await session.execute(stmt)
        ids.append(result.scalar_one())

    return ids


async def upsert_officers(
    session: AsyncSession,
    company_id: uuid.UUID,
    items: list[CHOfficerItem],
) -> None:
    """
    Find-or-create Officer entities and upsert their appointments.

    Officers are matched by (name, officer_role) — CH does not provide a
    stable officer ID in the list endpoint.  Officers with name=None are
    skipped.

    Appointments are upserted by (company_id, officer_id, role, appointed_on).
    NOTE: when appointed_on is NULL, PostgreSQL treats NULL != NULL in a
    unique constraint, so multiple NULL-dated appointments for the same
    officer+company+role will not conflict and may accumulate.  This is a
    known Phase 3A limitation; a future migration can address it.
    """
    now = _now()

    for item in items:
        if item.name is None:
            log.warning(
                "Skipping officer with null name for company_id=%s (corporate entity?)",
                company_id,
            )
            continue

        # --- find or create Officer entity ---
        # Progressive match: always use (name, officer_role); append DOB year
        # and month when available to reduce false matches between namesakes.
        dob = item.date_of_birth
        match_conditions: list[Any] = [
            _officers.c.name == item.name,
            _officers.c.officer_role == item.officer_role,
        ]
        if dob is not None:
            match_conditions.append(_officers.c.date_of_birth_year == dob.year)
            if dob.month is not None:
                match_conditions.append(_officers.c.date_of_birth_month == dob.month)
        find_stmt = sa.select(_officers.c.id).where(sa.and_(*match_conditions))
        officer_id: uuid.UUID | None = (
            await session.execute(find_stmt)
        ).scalar_one_or_none()

        if officer_id is None:
            dob_month = dob.month if dob is not None else None
            dob_year = dob.year if dob is not None else None
            officer_values: dict[str, Any] = {
                "id": uuid.uuid4(),
                "name": item.name,
                "officer_role": item.officer_role,
                "nationality": item.nationality,
                "occupation": item.occupation,
                "country_of_residence": item.country_of_residence,
                "date_of_birth_month": dob_month,
                "date_of_birth_year": dob_year,
                "raw_payload": None,
                "updated_at": now,
            }
            ins = (
                pg_insert(_officers)
                .values(**officer_values)
                .returning(_officers.c.id)
            )
            officer_id = (await session.execute(ins)).scalar_one()

        # --- upsert appointment ---
        addr = item.address.model_dump(exclude_none=True) if item.address else None
        appt_values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "company_id": company_id,
            "officer_id": officer_id,
            "role": item.officer_role,
            "appointed_on": item.appointed_on,
            "resigned_on": item.resigned_on,
            "is_pre_1992_appointment": item.is_pre_1992_appointment,
            "address": addr,
            "source_last_checked_at": now,
            "raw_payload": None,
            "updated_at": now,
        }
        appt_update = {
            k: v
            for k, v in appt_values.items()
            if k not in ("id", "company_id", "officer_id", "role", "appointed_on")
        }
        appt_stmt = (
            pg_insert(_officer_appointments)
            .values(**appt_values)
            .on_conflict_do_update(
                index_elements=[
                    "company_id",
                    "officer_id",
                    "role",
                    "appointed_on",
                ],
                set_=appt_update,
            )
        )
        await session.execute(appt_stmt)


async def upsert_pscs(
    session: AsyncSession,
    company_id: uuid.UUID,
    items: list[CHPSCItem],
) -> None:
    """
    Find-or-create PSC records for a company.

    psc_records has no unique constraint beyond the PK, so we match on
    (company_id, name, notified_on) for individuals or
    (company_id, kind, notified_on) when name is absent.
    """
    now = _now()

    for item in items:
        dob_month = item.date_of_birth.month if item.date_of_birth else None
        dob_year = item.date_of_birth.year if item.date_of_birth else None
        addr = item.address.model_dump(exclude_none=True) if item.address else None

        # Build the lookup predicate
        if item.name is not None:
            match_pred = sa.and_(
                _psc_records.c.company_id == company_id,
                _psc_records.c.name == item.name,
                _psc_records.c.notified_on == item.notified_on,
            )
        else:
            match_pred = sa.and_(
                _psc_records.c.company_id == company_id,
                _psc_records.c.kind == item.kind,
                _psc_records.c.notified_on == item.notified_on,
            )

        existing_id: uuid.UUID | None = (
            await session.execute(sa.select(_psc_records.c.id).where(match_pred))
        ).scalar_one_or_none()

        psc_values: dict[str, Any] = {
            "company_id": company_id,
            "kind": item.kind,
            "name": item.name,
            "notified_on": item.notified_on,
            "ceased_on": item.ceased_on,
            "nationality": item.nationality,
            "country_of_residence": item.country_of_residence,
            "date_of_birth_month": dob_month,
            "date_of_birth_year": dob_year,
            "natures_of_control": item.natures_of_control,
            "address": addr,
            "raw_payload": None,
            "source_last_checked_at": now,
            "updated_at": now,
        }

        if existing_id is None:
            await session.execute(
                pg_insert(_psc_records).values(id=uuid.uuid4(), **psc_values)
            )
        else:
            await session.execute(
                sa.update(_psc_records)
                .where(_psc_records.c.id == existing_id)
                .values(**psc_values)
            )


async def upsert_charges(
    session: AsyncSession,
    company_id: uuid.UUID,
    items: list[CHChargeItem],
) -> None:
    """
    Upsert registered charges for a company.

    Conflict key: (company_id, charge_id).
    charge_id = charge_code when present, else str(charge_number).
    Charges with neither field are skipped.
    """
    now = _now()

    for item in items:
        if item.charge_code:
            charge_id = item.charge_code
        elif item.charge_number is not None:
            charge_id = str(item.charge_number)
        else:
            log.warning(
                "Skipping charge with no charge_code or charge_number for company_id=%s",
                company_id,
            )
            continue

        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "company_id": company_id,
            "charge_id": charge_id,
            "status": item.status,
            "resolved_on": item.satisfied_on,
            "delivered_on": item.delivered_on,
            "created_on": item.created_on,
            "persons_entitled": item.persons_entitled,
            "particulars": item.particulars,
            "raw_payload": None,
            "source_last_checked_at": now,
            "updated_at": now,
        }
        update_set = {
            k: v
            for k, v in values.items()
            if k not in ("id", "company_id", "charge_id")
        }
        stmt = (
            pg_insert(_charges)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["company_id", "charge_id"],
                set_=update_set,
            )
        )
        await session.execute(stmt)


# ---------------------------------------------------------------------------
# Filing document upsert / status helpers
# ---------------------------------------------------------------------------


async def get_pending_filings_with_documents(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Return filings that have a document_metadata link, belong to the
    'accounts' category, and do not yet have a fetched filing_document row.

    Returns list of dicts: filing_id (UUID), transaction_id (str), source_links (dict).
    """
    result = await session.execute(
        sa.text(
            """
            SELECT f.id        AS filing_id,
                   f.transaction_id,
                   f.source_links
            FROM   filings f
            WHERE  f.company_id = :company_id
              AND  f.category   = 'accounts'
              AND  (f.source_links ? 'document_metadata')
              AND  NOT EXISTS (
                       SELECT 1
                       FROM   filing_documents fd
                       WHERE  fd.filing_id    = f.id
                         AND  fd.fetch_status = 'fetched'
                   )
            """
        ),
        {"company_id": str(company_id)},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def upsert_document_metadata(
    session: AsyncSession,
    filing_id: uuid.UUID,
    document_id: str,
    metadata: CHDocumentMetadata,
) -> uuid.UUID:
    """
    Create or refresh a filing_documents row for this document_id.

    On conflict (document_id unique): updates metadata columns but does NOT
    change fetch_status or storage fields — those are owned by mark_document_*.
    Initialises fetch_status='pending' only on INSERT.

    Returns the filing_document UUID.
    """
    now = _now()
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "filing_id": filing_id,
        "document_id": document_id,
        "original_filename": metadata.filename,
        "content_length": metadata.content_length,
        "content_type": metadata.content_type,
        "available_content_types": metadata.available_content_types or [],
        "fetch_status": "pending",
        "parse_status": "pending",
        "metadata_payload": metadata.model_dump(exclude_none=True),
        "updated_at": now,
    }
    # On conflict, refresh metadata fields only — do not reset fetch_status.
    update_set: dict[str, Any] = {
        "original_filename": values["original_filename"],
        "content_length": values["content_length"],
        "content_type": values["content_type"],
        "available_content_types": values["available_content_types"],
        "metadata_payload": values["metadata_payload"],
        "updated_at": now,
    }
    stmt = (
        pg_insert(_filing_documents)
        .values(**values)
        .on_conflict_do_update(index_elements=["document_id"], set_=update_set)
        .returning(_filing_documents.c.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def mark_document_fetched(
    session: AsyncSession,
    document_id: str,
    storage_key: str,
    storage_etag: str,
    content_type: str,
    content_length: int,
    downloaded_at: datetime,
) -> None:
    """
    Mark a filing_documents row as successfully fetched.

    Sets fetch_status='fetched' and records storage location details.
    """
    await session.execute(
        sa.update(_filing_documents)
        .where(_filing_documents.c.document_id == document_id)
        .values(
            fetch_status="fetched",
            storage_key=storage_key,
            storage_etag=storage_etag,
            content_type=content_type,
            content_length=content_length,
            downloaded_at=downloaded_at,
            updated_at=_now(),
        )
    )


async def mark_document_failed(
    session: AsyncSession,
    document_id: str,
) -> None:
    """
    Mark a filing_documents row as failed.

    Leaves the row in a retriable state — the next fetch_documents run
    will include it in the pending query and retry.
    """
    await session.execute(
        sa.update(_filing_documents)
        .where(_filing_documents.c.document_id == document_id)
        .values(fetch_status="failed", updated_at=_now())
    )


# ---------------------------------------------------------------------------
# Refresh run audit
# ---------------------------------------------------------------------------


async def create_refresh_run(
    company_id: Optional[uuid.UUID],
    trigger_type: str,
) -> uuid.UUID:
    """
    Insert a refresh_runs row with status='running' in its own session.

    Uses an independent session so the record is committed immediately and
    remains visible even if the main ingestion transaction later rolls back.
    Returns the new run UUID.
    """
    from app.db import get_session  # deferred: avoids circular import at module load

    run_id = uuid.uuid4()
    now = _now()
    async with get_session() as session:
        await session.execute(
            pg_insert(_refresh_runs).values(
                id=run_id,
                company_id=company_id,
                trigger_type=trigger_type,
                status="running",
                started_at=now,
            )
        )
        await session.commit()
    return run_id


async def finish_refresh_run(
    run_id: uuid.UUID,
    status: str,
    error_summary: Optional[str] = None,
) -> None:
    """
    Update a refresh_runs row with final status and finished_at timestamp.

    Uses an independent session so this write survives a rolled-back main
    transaction.  status should be 'completed' or 'failed'.
    """
    from app.db import get_session  # deferred: avoids circular import at module load

    now = _now()
    async with get_session() as session:
        await session.execute(
            sa.update(_refresh_runs)
            .where(_refresh_runs.c.id == run_id)
            .values(status=status, finished_at=now, error_summary=error_summary)
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Parser pipeline — document selection and extraction-run lifecycle
# ---------------------------------------------------------------------------


async def get_documents_ready_for_parse(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Return filing_documents that have been fetched and are ready for
    format classification (Phase 5A) or extraction (Phase 5B).

    Eligibility:
        fetch_status = 'fetched'
        parse_status IN ('pending', 'failed')

    'classified' and 'parsed' are excluded — they have already been
    processed.  'unsupported' is excluded — it is a terminal state.
    'failed' is included so transient errors are retried on the next run.

    Returns a list of dicts with keys:
        filing_document_id (UUID), document_id (str), content_type (str|None),
        available_content_types (list[str]|None), storage_key (str|None),
        filing_id (UUID), company_number (str)
    """
    result = await session.execute(
        sa.text(
            """
            SELECT
                fd.id                       AS filing_document_id,
                fd.document_id,
                fd.content_type,
                fd.available_content_types,
                fd.storage_key,
                fd.filing_id,
                c.company_number
            FROM   filing_documents fd
            JOIN   filings f  ON f.id  = fd.filing_id
            JOIN   companies c ON c.id = f.company_id
            WHERE  f.company_id    = :company_id
              AND  fd.fetch_status = 'fetched'
              AND  fd.parse_status IN ('pending', 'failed')
            ORDER  BY fd.created_at ASC
            """
        ),
        {"company_id": str(company_id)},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def create_extraction_run(
    filing_id: uuid.UUID,
    filing_document_id: uuid.UUID,
    document_format: str,
    parser_version: str,
) -> uuid.UUID:
    """
    Insert an extraction_runs row with status='running' in its own session.

    Uses an independent session so the record is committed immediately and
    remains visible even if the calling task later raises an exception.
    Returns the new extraction run UUID.
    """
    from app.db import get_session  # deferred: avoids circular import at module load

    run_id = uuid.uuid4()
    now = _now()
    async with get_session() as session:
        await session.execute(
            pg_insert(_extraction_runs).values(
                id=run_id,
                filing_id=filing_id,
                filing_document_id=filing_document_id,
                parser_version=parser_version,
                document_format=document_format,
                status="running",
                started_at=now,
            )
        )
        await session.commit()
    return run_id


async def finish_extraction_run(
    run_id: uuid.UUID,
    status: str,
    errors: Optional[dict[str, Any]] = None,
    confidence: Optional[Any] = None,
    warnings: Optional[list[str]] = None,
) -> None:
    """
    Update an extraction_runs row with final status, finished_at, and
    optional aggregate confidence and warning list.

    Uses an independent session.
    status should be 'completed', 'unsupported', or 'failed'.
    confidence is the aggregate Decimal run confidence (0.0–1.0).
    errors and warnings are free-form dicts/lists stored as JSONB.
    """
    from app.db import get_session  # deferred: avoids circular import at module load

    now = _now()
    values: dict[str, Any] = {"status": status, "finished_at": now, "errors": errors}
    if confidence is not None:
        values["confidence"] = confidence
    if warnings is not None:
        values["warnings"] = warnings

    async with get_session() as session:
        await session.execute(
            sa.update(_extraction_runs)
            .where(_extraction_runs.c.id == run_id)
            .values(**values)
        )
        await session.commit()


async def update_document_parse_status(
    session: AsyncSession,
    document_id: str,
    parse_status: str,
    document_format: Optional[str] = None,
) -> None:
    """
    Update filing_documents.parse_status (and optionally document_format).

    Used by the parse pipeline to advance the document through its lifecycle:
        pending  → classified   (format detected; Phase 5A)
        pending  → unsupported  (format not extractable; terminal)
        pending  → failed       (transient error; eligible for retry)
        classified → parsed     (extraction complete; Phase 5B)

    document_format is written when classification succeeds.  It is preserved
    on the row so Phase 5B can select the correct extraction path without
    re-classifying.
    """
    update_values: dict[str, Any] = {
        "parse_status": parse_status,
        "updated_at": _now(),
    }
    if document_format is not None:
        update_values["document_format"] = document_format

    await session.execute(
        sa.update(_filing_documents)
        .where(_filing_documents.c.document_id == document_id)
        .values(**update_values)
    )


# ---------------------------------------------------------------------------
# Financial fact persistence
# ---------------------------------------------------------------------------


async def get_classified_documents_for_extraction(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """
    Return filing_documents that have been classified and are ready for
    financial fact extraction.

    Eligibility:
        fetch_status = 'fetched'
        parse_status = 'classified'
        document_format IN ('ixbrl', 'xbrl', 'html')

    Returns dicts with keys:
        filing_document_id (UUID), document_id (str), document_format (str),
        content_type (str|None), storage_key (str), filing_id (UUID),
        company_number (str), action_date (date|None), transaction_id (str)
    """
    result = await session.execute(
        sa.text(
            """
            SELECT
                fd.id                AS filing_document_id,
                fd.document_id,
                fd.document_format,
                fd.content_type,
                fd.storage_key,
                fd.filing_id,
                c.company_number,
                f.action_date,
                f.transaction_id
            FROM   filing_documents fd
            JOIN   filings f  ON f.id  = fd.filing_id
            JOIN   companies c ON c.id = f.company_id
            WHERE  f.company_id      = :company_id
              AND  fd.fetch_status   = 'fetched'
              AND  fd.parse_status   = 'classified'
              AND  fd.document_format IN ('ixbrl', 'xbrl', 'html')
            ORDER  BY fd.created_at ASC
            """
        ),
        {"company_id": str(company_id)},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def upsert_financial_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    filing_id: uuid.UUID,
    source_document_id: uuid.UUID,
    period_start: Optional[Any],
    period_end: Any,
    accounts_type: Optional[str],
    currency_code: str,
    extraction_confidence: Any,
) -> uuid.UUID:
    """
    Insert or update a financial_periods row.

    Conflict key: (company_id, period_end, accounts_type).
    accounts_type=None is normalised to 'unknown' so the unique constraint
    (which uses NULLS DISTINCT) operates correctly.

    On conflict, updates extraction_confidence and source_document_id so
    the most recent extraction owns the period record.

    Returns the financial_period UUID.
    """
    # Normalise None → 'unknown' to make the unique constraint reliable.
    at = accounts_type or "unknown"

    # Calculate period length when both dates are available.
    period_length_days: Optional[int] = None
    if period_start is not None and period_end is not None:
        from datetime import date as _date

        if isinstance(period_start, _date) and isinstance(period_end, _date):
            period_length_days = (period_end - period_start).days

    now = _now()
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "company_id": company_id,
        "filing_id": filing_id,
        "period_start": period_start,
        "period_end": period_end,
        "period_length_days": period_length_days,
        "accounts_type": at,
        "currency_code": currency_code,
        "is_restated": False,
        "source_document_id": source_document_id,
        "extraction_confidence": extraction_confidence,
        "updated_at": now,
    }
    update_set: dict[str, Any] = {
        "period_start": period_start,
        "period_length_days": period_length_days,
        "source_document_id": source_document_id,
        "extraction_confidence": extraction_confidence,
        "updated_at": now,
    }
    stmt = (
        pg_insert(_financial_periods)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_financial_periods",
            set_=update_set,
        )
        .returning(_financial_periods.c.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def upsert_financial_facts(
    session: AsyncSession,
    period_id: uuid.UUID,
    company_id: uuid.UUID,
    source_document_id: uuid.UUID,
    source_filing_id: uuid.UUID,
    facts: list[Any],
) -> int:
    """
    Upsert canonical financial facts for one extraction run.

    Only persists facts where:
        canonical_name is not None
        fact_value is not None  (never store None as zero)

    Conflict key: (financial_period_id, fact_name).
    On conflict, overwrites with the new values — the most recent
    extraction wins.

    Returns the number of facts persisted.
    """
    now = _now()
    count = 0
    for fact in facts:
        if fact.canonical_name is None:
            continue  # unmapped — do not persist
        if fact.fact_value is None:
            continue  # unparseable value — never store as zero

        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "financial_period_id": period_id,
            "company_id": company_id,
            "fact_name": fact.canonical_name,
            "fact_value": fact.fact_value,
            "unit": fact.unit,
            "raw_label": fact.raw_label,
            "canonical_label": fact.canonical_name,
            "source_document_id": source_document_id,
            "source_filing_id": source_filing_id,
            "extraction_method": fact.mapping_method,
            "extraction_confidence": fact.extraction_confidence,
            "is_derived": False,
            "updated_at": now,
        }
        update_set: dict[str, Any] = {k: v for k, v in values.items() if k != "id"}
        stmt = (
            pg_insert(_financial_facts)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_financial_facts",
                set_=update_set,
            )
        )
        await session.execute(stmt)
        count += 1

    return count


# ---------------------------------------------------------------------------
# Phase 6A — derived metrics and risk signal persistence
# ---------------------------------------------------------------------------


async def upsert_derived_metrics(
    session: AsyncSession,
    company_id: uuid.UUID,
    financial_period_id: uuid.UUID,
    prior_period_id: Optional[uuid.UUID],
    results: list[Any],
    methodology_version: str,
) -> None:
    """
    Upsert derived metric rows for one analysis run.

    Conflict key: (company_id, financial_period_id, metric_key).
    On conflict, overwrites with the latest computed values.

    results is a list of MetricResult (from app.analytics.metrics).
    metric_value=None is stored as NULL (not zero).
    """
    now = _now()
    for result in results:
        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "company_id": company_id,
            "financial_period_id": financial_period_id,
            "prior_period_id": prior_period_id,
            "metric_key": result.metric_key,
            "metric_value": result.metric_value,
            "unit": result.unit,
            "confidence": result.confidence,
            "confidence_band": result.confidence_band,
            "warnings": result.warnings if result.warnings else None,
            "methodology_version": methodology_version,
            "generated_at": now,
        }
        update_set = {k: v for k, v in values.items() if k not in ("id", "company_id")}
        stmt = (
            pg_insert(_derived_metrics)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_derived_metrics",
                set_=update_set,
            )
        )
        await session.execute(stmt)


async def upsert_risk_signals(
    session: AsyncSession,
    company_id: uuid.UUID,
    results: list[Any],
    methodology_version: str,
) -> None:
    """
    Upsert risk signal rows based on the latest signal evaluation.

    For each SignalResult:
      fired=True  → INSERT status='active' / ON CONFLICT update last_confirmed_at
      fired=False → UPDATE status='resolved' for any existing active row

    Conflict key: (company_id, signal_code) — added in migration 0006.
    results is a list of SignalResult (from app.analytics.signals).
    """
    now = _now()
    for result in results:
        if result.fired:
            values: dict[str, Any] = {
                "id": uuid.uuid4(),
                "company_id": company_id,
                "signal_code": result.signal_code,
                "signal_name": result.signal_name,
                "category": result.category,
                "severity": result.severity,
                "status": "active",
                "explanation": result.explanation,
                "evidence": result.evidence,
                "methodology_version": methodology_version,
                "first_detected_at": now,
                "last_confirmed_at": now,
                "resolved_at": None,
                "updated_at": now,
            }
            update_set: dict[str, Any] = {
                "signal_name": result.signal_name,
                "severity": result.severity,
                "status": "active",
                "explanation": result.explanation,
                "evidence": result.evidence,
                "methodology_version": methodology_version,
                "last_confirmed_at": now,
                "resolved_at": None,
                "updated_at": now,
            }
            stmt = (
                pg_insert(_risk_signals)
                .values(**values)
                .on_conflict_do_update(
                    constraint="uq_risk_signals",
                    set_=update_set,
                )
            )
            await session.execute(stmt)
        else:
            # Resolve any existing active row for this signal.
            await session.execute(
                sa.update(_risk_signals)
                .where(
                    sa.and_(
                        _risk_signals.c.company_id == company_id,
                        _risk_signals.c.signal_code == result.signal_code,
                        _risk_signals.c.status == "active",
                    )
                )
                .values(
                    status="resolved",
                    resolved_at=now,
                    last_confirmed_at=now,
                    updated_at=now,
                )
            )


async def upsert_company_snapshot(
    session: AsyncSession,
    company_id: uuid.UUID,
    snapshot_payload: dict,
    methodology_version: str,
    parser_version: str,
    freshness_status: str = "current",
    snapshot_version: int = 1,
) -> uuid.UUID:
    """
    Replace the current snapshot for a company.

    1. Marks any existing is_current=true row as is_current=false.
    2. Inserts a new row with is_current=true.

    Returns the new snapshot UUID.
    Does not commit; the caller is responsible for commit.
    """
    now = _now()

    # Retire the existing current snapshot (if any).
    await session.execute(
        sa.update(_company_snapshots)
        .where(
            sa.and_(
                _company_snapshots.c.company_id == company_id,
                _company_snapshots.c.is_current.is_(True),
            )
        )
        .values(is_current=False)
    )

    new_id = uuid.uuid4()
    await session.execute(
        sa.insert(_company_snapshots).values(
            id=new_id,
            company_id=company_id,
            snapshot_version=snapshot_version,
            methodology_version=methodology_version,
            parser_version=parser_version,
            freshness_status=freshness_status,
            snapshot_payload=snapshot_payload,
            snapshot_generated_at=now,
            source_last_checked_at=now,
            is_current=True,
            created_at=now,
        )
    )
    return new_id
