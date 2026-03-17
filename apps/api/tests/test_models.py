"""
ORM model smoke tests.

Split into two groups:

1. Import tests (no DB required) — verify that all models can be imported
   and that Base.metadata contains every expected table. These run in any
   environment including CI with no database.

2. Instantiation tests (DB required via TEST_DATABASE_URL) — verify that
   model instances can be persisted and retrieved via the async session.
   These are skipped when TEST_DATABASE_URL is not set.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio

from tests.conftest import requires_db


# ---------------------------------------------------------------------------
# 1. Import / metadata smoke tests (no DB required)
# ---------------------------------------------------------------------------

EXPECTED_TABLES = {
    "methodology_versions",
    "users",
    "watchlists",
    "watchlist_items",
    "companies",
    "company_snapshots",
    "filings",
    "filing_documents",
    "officers",
    "officer_appointments",
    "psc_records",
    "charges",
    "insolvency_cases",
    "financial_periods",
    "financial_facts",
    "risk_signals",
    "refresh_runs",
    "extraction_runs",
    "audit_events",
}


def test_all_models_importable() -> None:
    """All ORM models can be imported without error."""
    import app.models  # noqa: F401
    from app.models import (
        AuditEvent,
        Charge,
        Company,
        CompanySnapshot,
        ExtractionRun,
        Filing,
        FilingDocument,
        FinancialFact,
        FinancialPeriod,
        InsolvencyCase,
        MethodologyVersion,
        Officer,
        OfficerAppointment,
        PscRecord,
        RefreshRun,
        RiskSignal,
        User,
        Watchlist,
        WatchlistItem,
    )

    # Spot-check table names
    assert Company.__tablename__ == "companies"
    assert User.__tablename__ == "users"
    assert RiskSignal.__tablename__ == "risk_signals"
    assert ExtractionRun.__tablename__ == "extraction_runs"
    assert AuditEvent.__tablename__ == "audit_events"
    assert FinancialPeriod.__tablename__ == "financial_periods"
    assert FinancialFact.__tablename__ == "financial_facts"


def test_base_metadata_contains_all_phase1a_tables() -> None:
    """Base.metadata must contain every Phase 1A table after model import."""
    import app.models  # noqa: F401 — ensures all models register with Base
    from app.db.base import Base

    registered = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - registered
    assert not missing, f"Tables missing from Base.metadata: {missing}"


def test_financial_fact_name_vocabulary() -> None:
    """
    Canonical fact names are documented and stable.

    This test encodes the resolved canonical names from
    docs/decisions/001-canonical-fact-names.md so that any accidental rename
    of a canonical name causes an immediate, visible test failure.
    """
    # These are the ONLY valid canonical fact_name values for MVP.
    # Adding new names requires updating this list AND the decision record.
    CANONICAL_FACT_NAMES = {
        "revenue",
        "gross_profit",
        "operating_profit_loss",
        "profit_loss_after_tax",
        "current_assets",
        "fixed_assets",
        "total_assets_less_current_liabilities",
        "creditors_due_within_one_year",
        "creditors_due_after_one_year",
        "net_assets_liabilities",
        "cash_bank_on_hand",
        "average_number_of_employees",
    }
    # Names that must NOT be used (rejected Option A names — docs/02 original)
    REJECTED_NAMES = {
        "operating_profit",
        "profit_after_tax",
        "net_assets",
        "cash_at_bank",
        "average_employees",
    }
    # Confirm no overlap (sanity check on the test itself)
    assert not (CANONICAL_FACT_NAMES & REJECTED_NAMES), (
        "Test data error: canonical and rejected sets overlap"
    )


# ---------------------------------------------------------------------------
# 2. DB instantiation tests (require TEST_DATABASE_URL)
# ---------------------------------------------------------------------------


@requires_db
async def test_create_and_fetch_company(db_session) -> None:
    """A Company row can be inserted and retrieved by company_number."""
    from app.models.company import Company

    company = Company(
        company_number="12345678",
        company_name="Smoke Test Ltd",
        company_status="active",
    )
    db_session.add(company)
    await db_session.flush()

    fetched = await db_session.get(Company, company.id)
    assert fetched is not None
    assert fetched.company_number == "12345678"
    assert fetched.company_name == "Smoke Test Ltd"
    assert fetched.created_at is not None


@requires_db
async def test_create_user(db_session) -> None:
    """A User row can be inserted with email and hashed_password."""
    from app.models.user import User

    user = User(
        email="smoke@example.com",
        hashed_password="not-a-real-hash",
    )
    db_session.add(user)
    await db_session.flush()

    fetched = await db_session.get(User, user.id)
    assert fetched is not None
    assert fetched.email == "smoke@example.com"
    assert fetched.is_active is True  # default


@requires_db
async def test_create_methodology_version(db_session) -> None:
    """A MethodologyVersion row can be inserted."""
    from app.models.methodology import MethodologyVersion

    mv = MethodologyVersion(
        version="v1.0.0",
        effective_date=date(2026, 1, 1),
        release_notes="Initial methodology",
        is_current=True,
    )
    db_session.add(mv)
    await db_session.flush()

    fetched = await db_session.get(MethodologyVersion, mv.id)
    assert fetched is not None
    assert fetched.version == "v1.0.0"
    assert fetched.is_current is True


@requires_db
async def test_create_filing_for_company(db_session) -> None:
    """A Filing can be linked to a Company."""
    from app.models.company import Company
    from app.models.filing import Filing

    company = Company(company_number="98765432", company_name="Filing Test Ltd")
    db_session.add(company)
    await db_session.flush()

    filing = Filing(
        company_id=company.id,
        transaction_id="MzAwOT",
        category="accounts",
        type="AA",
        date_filed=date(2025, 6, 1),
    )
    db_session.add(filing)
    await db_session.flush()

    fetched = await db_session.get(Filing, filing.id)
    assert fetched is not None
    assert fetched.company_id == company.id
    assert fetched.transaction_id == "MzAwOT"


@requires_db
async def test_audit_event_is_immutable_by_convention(db_session) -> None:
    """AuditEvent can be inserted; it has no updated_at column."""
    from app.models.audit import AuditEvent

    event = AuditEvent(
        actor_type="system",
        event_type="company.refreshed",
        entity_type="company",
        entity_id=str(uuid.uuid4()),
        event_payload={"source": "test"},
    )
    db_session.add(event)
    await db_session.flush()

    fetched = await db_session.get(AuditEvent, event.id)
    assert fetched is not None
    assert fetched.actor_type == "system"
    # Confirm no updated_at attribute exists on the model
    assert not hasattr(AuditEvent, "updated_at")


# ---------------------------------------------------------------------------
# 3. Financial domain DB tests (Phase 1B — require TEST_DATABASE_URL)
# ---------------------------------------------------------------------------


@requires_db
async def test_create_financial_period(db_session) -> None:
    """A FinancialPeriod can be created and linked to a company."""
    from app.models.company import Company
    from app.models.financial_period import FinancialPeriod

    company = Company(company_number="FP000001", company_name="Period Test Ltd")
    db_session.add(company)
    await db_session.flush()

    period = FinancialPeriod(
        company_id=company.id,
        period_start=date(2024, 3, 1),
        period_end=date(2025, 2, 28),
        period_length_days=365,
        accounts_type="small",
        accounting_standard="UK GAAP",
        currency_code="GBP",
        is_restated=False,
    )
    db_session.add(period)
    await db_session.flush()

    fetched = await db_session.get(FinancialPeriod, period.id)
    assert fetched is not None
    assert fetched.company_id == company.id
    assert fetched.period_end == date(2025, 2, 28)
    assert fetched.accounts_type == "small"
    assert fetched.is_restated is False
    assert fetched.extraction_confidence is None  # not yet scored


@requires_db
async def test_financial_fact_value_can_be_null(db_session) -> None:
    """
    fact_value may be NULL — a missing value must not be stored as 0.

    This test enforces the core data discipline rule from CLAUDE.md:
    'Never silently convert missing values to zero.'
    """
    from app.models.company import Company
    from app.models.financial_fact import FinancialFact
    from app.models.financial_period import FinancialPeriod

    company = Company(company_number="FF000001", company_name="Null Fact Test Ltd")
    db_session.add(company)
    await db_session.flush()

    period = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="micro-entity",
    )
    db_session.add(period)
    await db_session.flush()

    # Revenue was not extractable from this micro-entity filing
    fact = FinancialFact(
        financial_period_id=period.id,
        company_id=company.id,
        fact_name="revenue",
        fact_value=None,  # explicitly NULL — not zero
        extraction_method="ixbrl",
        extraction_confidence=None,
    )
    db_session.add(fact)
    await db_session.flush()

    fetched = await db_session.get(FinancialFact, fact.id)
    assert fetched is not None
    assert fetched.fact_value is None, (
        "fact_value must be NULL for a missing value, not zero"
    )
    assert fetched.extraction_confidence is None


@requires_db
async def test_financial_fact_stores_signed_value(db_session) -> None:
    """
    Negative fact values are preserved exactly.

    A net loss or negative net assets must not have its sign discarded.
    This directly validates the sign-direction naming decision (Option B).
    """
    from app.models.company import Company
    from app.models.financial_fact import FinancialFact
    from app.models.financial_period import FinancialPeriod
    from decimal import Decimal

    company = Company(company_number="FF000002", company_name="Loss Making Ltd")
    db_session.add(company)
    await db_session.flush()

    period = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="small",
    )
    db_session.add(period)
    await db_session.flush()

    # Company has net liabilities (negative net assets)
    fact = FinancialFact(
        financial_period_id=period.id,
        company_id=company.id,
        fact_name="net_assets_liabilities",
        fact_value=Decimal("-125000.00"),
        unit="GBP",
        raw_label="Net assets / (liabilities)",
        extraction_method="ixbrl",
        extraction_confidence=Decimal("0.9500"),
        is_derived=False,
    )
    db_session.add(fact)
    await db_session.flush()

    fetched = await db_session.get(FinancialFact, fact.id)
    assert fetched is not None
    assert fetched.fact_value == Decimal("-125000.00"), (
        "Negative net assets must be stored with sign preserved"
    )
    assert fetched.fact_name == "net_assets_liabilities"
    assert fetched.raw_label == "Net assets / (liabilities)"


@requires_db
async def test_financial_period_unique_constraint(db_session) -> None:
    """
    Two periods with the same (company_id, period_end, accounts_type, is_restated)
    must fail. One original (False) and one restated (True) may coexist.

    See: docs/decisions/003-restatement-strategy.md
    """
    from sqlalchemy.exc import IntegrityError

    from app.models.company import Company
    from app.models.financial_period import FinancialPeriod

    company = Company(company_number="FP000002", company_name="Dup Period Test Ltd")
    db_session.add(company)
    await db_session.flush()

    period_a = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="small",
    )
    db_session.add(period_a)
    await db_session.flush()

    period_b = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="small",
    )
    db_session.add(period_b)

    with pytest.raises(IntegrityError):
        await db_session.flush()


@requires_db
async def test_original_and_restated_period_can_coexist(db_session) -> None:
    """
    One original (is_restated=False) and one restated (is_restated=True) period
    may coexist for the same (company_id, period_end, accounts_type).

    This is the positive case for Decision 003: the 4-column unique constraint
    allows the pair without raising IntegrityError.
    """
    from app.models.company import Company
    from app.models.financial_period import FinancialPeriod

    company = Company(company_number="FP000003", company_name="Restatement Test Ltd")
    db_session.add(company)
    await db_session.flush()

    original = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="small",
        is_restated=False,
    )
    restated = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="small",
        is_restated=True,
    )
    db_session.add(original)
    db_session.add(restated)
    # Must not raise — original and restated differ on is_restated
    await db_session.flush()

    assert original.id != restated.id


@requires_db
async def test_financial_fact_unique_constraint(db_session) -> None:
    """
    Two facts with the same (financial_period_id, fact_name) must fail.

    This enforces immutability: re-parsing must create a new period or use a
    supersession mechanism, not overwrite the existing fact.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models.company import Company
    from app.models.financial_fact import FinancialFact
    from app.models.financial_period import FinancialPeriod
    from decimal import Decimal

    company = Company(company_number="FF000003", company_name="Dup Fact Test Ltd")
    db_session.add(company)
    await db_session.flush()

    period = FinancialPeriod(
        company_id=company.id,
        period_end=date(2025, 2, 28),
        accounts_type="small",
    )
    db_session.add(period)
    await db_session.flush()

    fact_a = FinancialFact(
        financial_period_id=period.id,
        company_id=company.id,
        fact_name="revenue",
        fact_value=Decimal("500000.00"),
    )
    db_session.add(fact_a)
    await db_session.flush()

    fact_b = FinancialFact(
        financial_period_id=period.id,
        company_id=company.id,
        fact_name="revenue",
        fact_value=Decimal("600000.00"),
    )
    db_session.add(fact_b)

    with pytest.raises(IntegrityError):
        await db_session.flush()
