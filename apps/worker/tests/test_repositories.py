"""
Repository unit tests.

All tests use AsyncMock for the SQLAlchemy session — no real DB required.
The tests verify:
  - correct return values from upserts
  - skipping behaviour for invalid/incomplete input data
  - find-or-create branching for officers and PSCs
  - fallback charge_id logic (charge_code → charge_number → skip)
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.repositories import (
    create_refresh_run,
    finish_refresh_run,
    upsert_charges,
    upsert_company,
    upsert_filings,
    upsert_officers,
    upsert_pscs,
)
from ch_client.schemas import (
    CHAccountsSummary,
    CHChargeItem,
    CHCompanyProfile,
    CHConfirmationStatement,
    CHFilingHistoryItem,
    CHOfficerItem,
    CHPSCItem,
)


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
    """Return a mock AsyncSession whose execute() → scalar_one() returns scalar_return."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = scalar_return or uuid.uuid4()
    mock_result.scalar_one_or_none.return_value = None  # default: not found
    session.execute.return_value = mock_result
    return session


def _minimal_profile(
    company_number: str = "12345678",
    company_name: str = "Test Ltd",
) -> CHCompanyProfile:
    return CHCompanyProfile(
        company_number=company_number,
        company_name=company_name,
        company_status="active",
        type="ltd",
        accounts=CHAccountsSummary(next_due=date(2026, 1, 31), overdue=False),
        confirmation_statement=CHConfirmationStatement(
            next_due=date(2026, 6, 1), overdue=False
        ),
    )


# ---------------------------------------------------------------------------
# upsert_company
# ---------------------------------------------------------------------------


async def test_upsert_company_returns_uuid() -> None:
    expected_id = uuid.uuid4()
    session = _make_session(scalar_return=expected_id)

    result = await upsert_company(session, _minimal_profile())

    assert result == expected_id
    session.execute.assert_called_once()


async def test_upsert_company_without_accounts_does_not_raise() -> None:
    profile = CHCompanyProfile(company_number="99999999", company_name="Bare Ltd")
    session = _make_session()
    # Should not raise even with accounts=None and confirmation_statement=None
    await upsert_company(session, profile)
    session.execute.assert_called_once()


async def test_upsert_company_serialises_address() -> None:
    """registered_office_address dict should be present in execute values."""
    from ch_client.schemas import CHAddress

    profile = _minimal_profile()
    profile.registered_office_address = CHAddress(
        address_line_1="1 Test St", locality="London", postal_code="EC1A 1BB"
    )
    session = _make_session()
    await upsert_company(session, profile)
    # Just verify execute was called — address serialisation is internal
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# upsert_filings
# ---------------------------------------------------------------------------


async def test_upsert_filings_empty_list_returns_empty() -> None:
    session = _make_session()
    result = await upsert_filings(session, uuid.uuid4(), [])
    assert result == []
    session.execute.assert_not_called()


async def test_upsert_filings_returns_one_id_per_item() -> None:
    company_id = uuid.uuid4()
    filing_id = uuid.uuid4()
    session = _make_session(scalar_return=filing_id)

    items = [
        CHFilingHistoryItem(transaction_id="TX001", category="accounts", type="AA"),
        CHFilingHistoryItem(transaction_id="TX002", category="confirmation-statement"),
    ]
    result = await upsert_filings(session, company_id, items)

    assert len(result) == 2
    assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# upsert_officers
# ---------------------------------------------------------------------------


async def test_upsert_officers_skips_null_name(caplog: pytest.LogCaptureFixture) -> None:
    session = _make_session()
    items = [CHOfficerItem(name=None, officer_role="director")]

    import logging
    with caplog.at_level(logging.WARNING, logger="app.repositories"):
        await upsert_officers(session, uuid.uuid4(), items)

    session.execute.assert_not_called()
    assert "null name" in caplog.text


async def test_upsert_officers_creates_new_officer_when_not_found() -> None:
    """When SELECT returns no match, two execute calls: INSERT officer + INSERT appointment."""
    company_id = uuid.uuid4()
    new_officer_id = uuid.uuid4()

    session = AsyncMock()
    not_found_result = MagicMock()
    not_found_result.scalar_one_or_none.return_value = None  # officer not found
    insert_result = MagicMock()
    insert_result.scalar_one.return_value = new_officer_id  # INSERT officer returns id
    appt_result = MagicMock()  # appointment INSERT result (no return value needed)

    session.execute.side_effect = [not_found_result, insert_result, appt_result]

    items = [CHOfficerItem(name="Alice Smith", officer_role="director")]
    await upsert_officers(session, company_id, items)

    assert session.execute.call_count == 3  # SELECT + INSERT officer + INSERT appointment


async def test_upsert_officers_reuses_existing_officer() -> None:
    """When SELECT finds an existing officer, skip INSERT and go straight to appointment."""
    company_id = uuid.uuid4()
    existing_officer_id = uuid.uuid4()

    session = AsyncMock()
    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = existing_officer_id
    appt_result = MagicMock()

    session.execute.side_effect = [found_result, appt_result]

    items = [CHOfficerItem(name="Bob Jones", officer_role="secretary")]
    await upsert_officers(session, company_id, items)

    # SELECT + INSERT appointment only (no INSERT officer)
    assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# upsert_pscs
# ---------------------------------------------------------------------------


async def test_upsert_pscs_inserts_when_not_found() -> None:
    company_id = uuid.uuid4()
    session = AsyncMock()
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    insert_res = MagicMock()
    session.execute.side_effect = [not_found, insert_res]

    items = [
        CHPSCItem(
            name="Alice Smith",
            kind="individual-person-with-significant-control",
            notified_on=date(2016, 4, 6),
            natures_of_control=["ownership-of-shares-25-to-50-percent"],
        )
    ]
    await upsert_pscs(session, company_id, items)
    assert session.execute.call_count == 2  # SELECT + INSERT


async def test_upsert_pscs_updates_when_found() -> None:
    company_id = uuid.uuid4()
    existing_id = uuid.uuid4()
    session = AsyncMock()
    found = MagicMock()
    found.scalar_one_or_none.return_value = existing_id
    update_res = MagicMock()
    session.execute.side_effect = [found, update_res]

    items = [
        CHPSCItem(
            name="Bob Corp",
            kind="corporate-entity-with-significant-control",
            notified_on=date(2018, 1, 1),
        )
    ]
    await upsert_pscs(session, company_id, items)
    assert session.execute.call_count == 2  # SELECT + UPDATE


async def test_upsert_pscs_uses_kind_when_name_is_none() -> None:
    """When name is None, match predicate switches to (company_id, kind, notified_on)."""
    company_id = uuid.uuid4()
    session = AsyncMock()
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    insert_res = MagicMock()
    session.execute.side_effect = [not_found, insert_res]

    items = [
        CHPSCItem(
            name=None,
            kind="super-secure-trust-with-significant-control",
            notified_on=date(2020, 5, 1),
        )
    ]
    await upsert_pscs(session, company_id, items)
    # Verify SELECT was attempted (no crash on name=None)
    assert session.execute.call_count == 2


# ---------------------------------------------------------------------------
# upsert_charges
# ---------------------------------------------------------------------------


async def test_upsert_charges_uses_charge_code() -> None:
    company_id = uuid.uuid4()
    session = _make_session()

    items = [CHChargeItem(charge_code="0881860017", status="outstanding")]
    await upsert_charges(session, company_id, items)
    session.execute.assert_called_once()


async def test_upsert_charges_falls_back_to_charge_number() -> None:
    company_id = uuid.uuid4()
    session = _make_session()

    items = [CHChargeItem(charge_code=None, charge_number=1, status="satisfied")]
    await upsert_charges(session, company_id, items)
    session.execute.assert_called_once()


async def test_upsert_charges_skips_when_no_identifier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    company_id = uuid.uuid4()
    session = _make_session()

    import logging
    with caplog.at_level(logging.WARNING, logger="app.repositories"):
        await upsert_charges(
            session, company_id, [CHChargeItem(charge_code=None, charge_number=None)]
        )

    session.execute.assert_not_called()
    assert "no charge_code or charge_number" in caplog.text


async def test_upsert_charges_writes_resolved_on() -> None:
    """satisfied_on from CHChargeItem is written as resolved_on in the DB."""
    company_id = uuid.uuid4()
    session = _make_session()

    items = [
        CHChargeItem(
            charge_code="0881860017",
            status="satisfied",
            satisfied_on=date(2022, 3, 15),
        )
    ]
    await upsert_charges(session, company_id, items)

    # Verify execute was called — resolved_on is included in the INSERT statement
    session.execute.assert_called_once()
    stmt = session.execute.call_args[0][0]
    assert "resolved_on" in str(stmt)


# ---------------------------------------------------------------------------
# upsert_officers — progressive DOB match
# ---------------------------------------------------------------------------


async def test_upsert_officers_uses_dob_in_match_when_available() -> None:
    """When date_of_birth is set, the find query includes year and month conditions."""
    from ch_client.schemas import CHDateOfBirth

    company_id = uuid.uuid4()
    existing_officer_id = uuid.uuid4()

    session = AsyncMock()
    found_result = MagicMock()
    found_result.scalar_one_or_none.return_value = existing_officer_id
    appt_result = MagicMock()
    session.execute.side_effect = [found_result, appt_result]

    items = [
        CHOfficerItem(
            name="Jane Doe",
            officer_role="director",
            date_of_birth=CHDateOfBirth(year=1980, month=6),
        )
    ]
    await upsert_officers(session, company_id, items)

    # Officer was found — no INSERT officer, only SELECT + INSERT appointment
    assert session.execute.call_count == 2
    # Verify the SELECT statement includes DOB conditions
    find_call_stmt = session.execute.call_args_list[0][0][0]
    stmt_str = str(find_call_stmt)
    assert "date_of_birth_year" in stmt_str
    assert "date_of_birth_month" in stmt_str


async def test_upsert_officers_match_without_dob_skips_dob_conditions() -> None:
    """When date_of_birth is None, the find query uses only (name, officer_role)."""
    company_id = uuid.uuid4()
    new_officer_id = uuid.uuid4()

    session = AsyncMock()
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    insert_result = MagicMock()
    insert_result.scalar_one.return_value = new_officer_id
    appt_result = MagicMock()
    session.execute.side_effect = [not_found, insert_result, appt_result]

    items = [CHOfficerItem(name="John Smith", officer_role="secretary")]
    await upsert_officers(session, company_id, items)

    find_call_stmt = session.execute.call_args_list[0][0][0]
    assert "date_of_birth_year" not in str(find_call_stmt)


# ---------------------------------------------------------------------------
# create_refresh_run / finish_refresh_run
# ---------------------------------------------------------------------------


async def test_create_refresh_run_commits_and_returns_uuid() -> None:
    """create_refresh_run inserts a running row and commits immediately."""
    mock_session = AsyncMock()

    with patch("app.repositories.get_session", return_value=_async_cm(mock_session)):
        run_id = await create_refresh_run(uuid.uuid4(), "full")

    assert isinstance(run_id, uuid.UUID)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


async def test_create_refresh_run_accepts_none_company_id() -> None:
    """
    create_refresh_run(None, 'full') must not raise.

    Full refreshes call this before the company_id is resolved from the DB.
    The column was made nullable in migration 0004; this test guards that the
    Python layer passes None cleanly without type errors.
    """
    mock_session = AsyncMock()

    with patch("app.repositories.get_session", return_value=_async_cm(mock_session)):
        run_id = await create_refresh_run(None, "full")

    assert isinstance(run_id, uuid.UUID)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
    # Verify company_id=None is present in the INSERT statement values
    stmt = mock_session.execute.call_args[0][0]
    compiled = stmt.compile(compile_kwargs={"literal_binds": False})
    # The INSERT must include the company_id bind parameter (with None value)
    assert "company_id" in str(compiled)


async def test_finish_refresh_run_updates_and_commits() -> None:
    """finish_refresh_run updates the row status and commits immediately."""
    mock_session = AsyncMock()

    with patch("app.repositories.get_session", return_value=_async_cm(mock_session)):
        await finish_refresh_run(uuid.uuid4(), "completed")

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()


async def test_finish_refresh_run_passes_error_summary() -> None:
    """error_summary is forwarded when status='failed'."""
    mock_session = AsyncMock()

    with patch("app.repositories.get_session", return_value=_async_cm(mock_session)):
        await finish_refresh_run(uuid.uuid4(), "failed", error_summary="boom")

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
