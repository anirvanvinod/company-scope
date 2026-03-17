"""Initial schema — Phase 1A core tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-17

Tables created (migration order per docs/02-database-schema.md §Migration order):

  + methodology_versions  [extension — not in docs/02; required by docs/06]
  + users
  + companies
  + watchlists
  + watchlist_items
  + filings
  + filing_documents
  + officers
  + officer_appointments
  + psc_records
  + charges
  + insolvency_cases
  + risk_signals
  + company_snapshots
  + refresh_runs
  + extraction_runs
  + audit_events

Deferred — blocked by docs/decisions/001-canonical-fact-names.md:
  - financial_periods
  - financial_facts

Deferred — not in Phase 1A scope:
  - alert_channels
  - metric_series_cache

Requires the citext extension for case-insensitive email storage on users.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # PostgreSQL extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # ------------------------------------------------------------------
    # methodology_versions
    # Extension table — not in docs/02; required by docs/06 §Versioning.
    # ------------------------------------------------------------------
    op.create_table(
        "methodology_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("release_notes", sa.Text()),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("version", name="uq_methodology_versions_version"),
    )

    # ------------------------------------------------------------------
    # users
    # Uses citext for case-insensitive email (extension enabled above).
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "email",
            sa.Text(),  # actual DB type is citext — set via raw DDL below
            nullable=False,
        ),
        sa.Column("display_name", sa.Text()),
        sa.Column("auth_provider", sa.String(32), nullable=False),
        sa.Column("auth_subject", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Alter email column to use citext for case-insensitive uniqueness
    op.execute("ALTER TABLE users ALTER COLUMN email TYPE citext USING email::citext")
    op.create_index("uq_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # companies
    # ------------------------------------------------------------------
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_number", sa.String(16), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.String(64)),
        sa.Column("company_status", sa.String(64)),
        sa.Column("company_type", sa.String(64)),
        sa.Column("subtype", sa.String(64)),
        sa.Column("date_of_creation", sa.Date()),
        sa.Column("cessation_date", sa.Date()),
        sa.Column("has_insolvency_history", sa.Boolean()),
        sa.Column("has_charges", sa.Boolean()),
        sa.Column("accounts_next_due", sa.Date()),
        sa.Column("accounts_overdue", sa.Boolean()),
        sa.Column("confirmation_statement_next_due", sa.Date()),
        sa.Column("confirmation_statement_overdue", sa.Boolean()),
        sa.Column("registered_office_address", postgresql.JSONB()),
        sa.Column("sic_codes", postgresql.ARRAY(sa.Text())),
        sa.Column("source_etag", sa.Text()),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("company_number", name="uq_companies_number"),
    )
    op.create_index(
        "idx_companies_name",
        "companies",
        [sa.text("to_tsvector('simple', company_name)")],
        postgresql_using="gin",
    )
    op.create_index("idx_companies_status", "companies", ["company_status"])

    # ------------------------------------------------------------------
    # watchlists
    # ------------------------------------------------------------------
    op.create_table(
        "watchlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_watchlists_user", "watchlists", ["user_id"])

    # ------------------------------------------------------------------
    # watchlist_items
    # ------------------------------------------------------------------
    op.create_table(
        "watchlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "watchlist_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("watchlists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "monitoring_status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "watchlist_id", "company_id", name="uq_watchlist_items"
        ),
    )
    op.create_index("idx_watchlist_items_company", "watchlist_items", ["company_id"])

    # ------------------------------------------------------------------
    # filings
    # ------------------------------------------------------------------
    op.create_table(
        "filings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("transaction_id", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64)),
        sa.Column("type", sa.String(32)),
        sa.Column("description", sa.Text()),
        sa.Column("description_values", postgresql.JSONB()),
        sa.Column("action_date", sa.Date()),
        sa.Column("date_filed", sa.Date()),
        sa.Column("pages", sa.Integer()),
        sa.Column("barcode", sa.Text()),
        sa.Column("paper_filed", sa.Boolean()),
        sa.Column("source_links", postgresql.JSONB()),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "company_id", "transaction_id", name="uq_filings_company_transaction"
        ),
    )
    op.create_index(
        "idx_filings_company_action_date",
        "filings",
        ["company_id", sa.text("action_date DESC")],
    )
    op.create_index("idx_filings_category", "filings", ["category"])
    op.create_index("idx_filings_type", "filings", ["type"])

    # ------------------------------------------------------------------
    # filing_documents
    # ------------------------------------------------------------------
    op.create_table(
        "filing_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_id", sa.String(128), nullable=False),
        sa.Column("original_filename", sa.Text()),
        sa.Column("content_length", sa.BigInteger()),
        sa.Column("content_type", sa.Text()),
        sa.Column("available_content_types", postgresql.ARRAY(sa.Text())),
        sa.Column("storage_key", sa.Text()),
        sa.Column("storage_etag", sa.Text()),
        sa.Column(
            "fetch_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "parse_status",
            sa.String(32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("downloaded_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("document_id", name="uq_filing_documents_document_id"),
    )
    op.create_index("idx_filing_documents_filing", "filing_documents", ["filing_id"])
    op.create_index(
        "idx_filing_documents_status",
        "filing_documents",
        ["fetch_status", "parse_status"],
    )

    # ------------------------------------------------------------------
    # officers
    # ------------------------------------------------------------------
    op.create_table(
        "officers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("officer_external_id", sa.Text()),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("officer_role", sa.String(64)),
        sa.Column("nationality", sa.Text()),
        sa.Column("occupation", sa.Text()),
        sa.Column("country_of_residence", sa.Text()),
        sa.Column("date_of_birth_month", sa.SmallInteger()),
        sa.Column("date_of_birth_year", sa.SmallInteger()),
        sa.Column("kind", sa.String(32)),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_officers_name",
        "officers",
        [sa.text("to_tsvector('simple', name)")],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # officer_appointments
    # ------------------------------------------------------------------
    op.create_table(
        "officer_appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "officer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("officers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("appointment_id", sa.Text()),
        sa.Column("role", sa.String(64)),
        sa.Column("appointed_on", sa.Date()),
        sa.Column("resigned_on", sa.Date()),
        sa.Column("is_pre_1992_appointment", sa.Boolean()),
        sa.Column("address", postgresql.JSONB()),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "officer_id",
            "role",
            "appointed_on",
            name="uq_officer_appointments",
        ),
    )
    op.create_index(
        "idx_officer_appointments_company", "officer_appointments", ["company_id"]
    )
    op.create_index(
        "idx_officer_appointments_active",
        "officer_appointments",
        ["company_id", "resigned_on"],
    )

    # ------------------------------------------------------------------
    # psc_records
    # ------------------------------------------------------------------
    op.create_table(
        "psc_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("psc_external_id", sa.Text()),
        sa.Column("kind", sa.String(64)),
        sa.Column("name", sa.Text()),
        sa.Column("notified_on", sa.Date()),
        sa.Column("ceased_on", sa.Date()),
        sa.Column("nationality", sa.Text()),
        sa.Column("country_of_residence", sa.Text()),
        sa.Column("date_of_birth_month", sa.SmallInteger()),
        sa.Column("date_of_birth_year", sa.SmallInteger()),
        sa.Column("natures_of_control", postgresql.ARRAY(sa.Text())),
        sa.Column("address", postgresql.JSONB()),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_psc_records_company", "psc_records", ["company_id"])
    op.create_index(
        "idx_psc_records_active", "psc_records", ["company_id", "ceased_on"]
    )

    # ------------------------------------------------------------------
    # charges
    # ------------------------------------------------------------------
    op.create_table(
        "charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("charge_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(64)),
        sa.Column("delivered_on", sa.Date()),
        sa.Column("created_on", sa.Date()),
        sa.Column("resolved_on", sa.Date()),
        sa.Column("persons_entitled", postgresql.JSONB()),
        sa.Column("particulars", postgresql.JSONB()),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("company_id", "charge_id", name="uq_charges"),
    )
    op.create_index("idx_charges_company", "charges", ["company_id"])
    op.create_index("idx_charges_status", "charges", ["status"])

    # ------------------------------------------------------------------
    # insolvency_cases
    # ------------------------------------------------------------------
    op.create_table(
        "insolvency_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_number", sa.Text()),
        sa.Column("case_type", sa.String(64)),
        sa.Column("petition_date", sa.Date()),
        sa.Column("order_date", sa.Date()),
        sa.Column("notes", postgresql.JSONB()),
        sa.Column("practitioner", postgresql.JSONB()),
        sa.Column("raw_payload", postgresql.JSONB()),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_insolvency_cases_company", "insolvency_cases", ["company_id"])

    # ------------------------------------------------------------------
    # risk_signals
    # ------------------------------------------------------------------
    op.create_table(
        "risk_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("signal_code", sa.String(64), nullable=False),
        sa.Column("signal_name", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="active"
        ),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB()),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_risk_signals_company",
        "risk_signals",
        ["company_id", "status", "severity"],
    )
    op.create_index("idx_risk_signals_code", "risk_signals", ["signal_code"])

    # ------------------------------------------------------------------
    # company_snapshots
    # ------------------------------------------------------------------
    op.create_table(
        "company_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("methodology_version", sa.String(32), nullable=False),
        sa.Column("parser_version", sa.String(32)),
        sa.Column("freshness_status", sa.String(32), nullable=False),
        sa.Column("snapshot_payload", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot_generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "is_current", sa.Boolean(), nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # Partial unique index: only one current snapshot per company
    op.create_index(
        "uq_company_snapshots_current",
        "company_snapshots",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "idx_company_snapshots_payload_gin",
        "company_snapshots",
        [sa.text("snapshot_payload")],
        postgresql_using="gin",
    )

    # ------------------------------------------------------------------
    # refresh_runs
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_summary", sa.Text()),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_refresh_runs_company",
        "refresh_runs",
        ["company_id", sa.text("started_at DESC")],
    )

    # ------------------------------------------------------------------
    # extraction_runs
    # ------------------------------------------------------------------
    op.create_table(
        "extraction_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "filing_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filing_documents.id", ondelete="SET NULL"),
        ),
        sa.Column("parser_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("warnings", postgresql.JSONB()),
        sa.Column("errors", postgresql.JSONB()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_extraction_runs_document",
        "extraction_runs",
        ["filing_document_id", sa.text("started_at DESC")],
    )

    # ------------------------------------------------------------------
    # audit_events
    # ------------------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("event_payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_audit_events_entity",
        "audit_events",
        ["entity_type", "entity_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_table("audit_events")
    op.drop_table("extraction_runs")
    op.drop_table("refresh_runs")
    op.drop_table("company_snapshots")
    op.drop_table("risk_signals")
    op.drop_table("insolvency_cases")
    op.drop_table("charges")
    op.drop_table("psc_records")
    op.drop_table("officer_appointments")
    op.drop_table("officers")
    op.drop_table("filing_documents")
    op.drop_table("filings")
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("companies")
    op.drop_table("users")
    op.drop_table("methodology_versions")
    op.execute("DROP EXTENSION IF EXISTS citext")
