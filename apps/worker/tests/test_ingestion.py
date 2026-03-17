"""
Ingestion orchestration unit tests.

Tests cover the async _*_async helper functions directly (not the Celery task
wrapper) since asyncio.run() is hard to unit-test and the logic is all in the
async layer.

Mocking strategy:
  - create_ch_client is patched to return an AsyncMock client
  - get_session is patched to return an AsyncMock session
  - Repository functions are patched to avoid actual DB calls

Pagination is tested by configuring mock responses with multiple pages.
"""

from __future__ import annotations

import uuid
from datetime import date
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ch_client.exceptions import CHAuthError, CHNotFoundError
from app.tasks.ingestion import (
    _fetch_charges_async,
    _fetch_filings_async,
    _fetch_officers_async,
    _fetch_pscs_async,
    _paginate,
    _refresh_company_async,
)
from ch_client.schemas import (
    CHChargeItem,
    CHChargesResponse,
    CHCompanyProfile,
    CHFilingHistoryItem,
    CHFilingHistoryResponse,
    CHOfficerItem,
    CHOfficersResponse,
    CHPSCItem,
    CHPSCsResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(company_number: str = "12345678") -> CHCompanyProfile:
    return CHCompanyProfile(
        company_number=company_number, company_name="Acme Ltd"
    )


def _async_cm(value: object) -> object:
    """Return an async context manager that yields *value*."""
    @asynccontextmanager
    async def _cm() -> AsyncGenerator[object, None]:
        yield value
    return _cm()


# ---------------------------------------------------------------------------
# _paginate
# ---------------------------------------------------------------------------


async def test_paginate_single_page() -> None:
    """If total_count equals items returned, only one call is made."""
    item = CHFilingHistoryItem(transaction_id="TX001")
    resp = CHFilingHistoryResponse(items=[item], total_count=1)
    mock_fn = AsyncMock(return_value=resp)

    result = await _paginate(mock_fn, "12345678", total_attr="total_count")

    assert result == [item]
    mock_fn.assert_called_once_with(
        "12345678", items_per_page=100, start_index=0
    )


async def test_paginate_two_pages() -> None:
    """When total > per_page, a second call is made with start_index=100."""
    items_p1 = [CHFilingHistoryItem(transaction_id=f"TX{i:03d}") for i in range(100)]
    items_p2 = [CHFilingHistoryItem(transaction_id="TX100")]

    resp_p1 = CHFilingHistoryResponse(items=items_p1, total_count=101)
    resp_p2 = CHFilingHistoryResponse(items=items_p2, total_count=101)

    mock_fn = AsyncMock(side_effect=[resp_p1, resp_p2])

    result = await _paginate(mock_fn, "12345678", total_attr="total_count")

    assert len(result) == 101
    assert mock_fn.call_count == 2
    mock_fn.assert_any_call("12345678", items_per_page=100, start_index=100)


async def test_paginate_stops_on_empty_items() -> None:
    """If resp.items is empty, stop even if start < total."""
    resp = CHFilingHistoryResponse(items=[], total_count=50)
    mock_fn = AsyncMock(return_value=resp)

    result = await _paginate(mock_fn, "12345678", total_attr="total_count")

    assert result == []
    mock_fn.assert_called_once()


# ---------------------------------------------------------------------------
# _refresh_company_async
# ---------------------------------------------------------------------------


async def test_refresh_company_async_calls_all_five_fetches() -> None:
    """
    Full orchestration smoke test.

    Verifies that get_company, get_filing_history, get_officers, get_pscs, and
    get_charges are all called, and that session.commit() is called once.
    """
    company_id = uuid.uuid4()
    mock_session = AsyncMock()

    mock_client = AsyncMock()
    mock_client.get_company.return_value = _make_profile()
    mock_client.get_filing_history.return_value = CHFilingHistoryResponse(
        items=[CHFilingHistoryItem(transaction_id="TX1")], total_count=1
    )
    mock_client.get_officers.return_value = CHOfficersResponse(
        items=[CHOfficerItem(name="Alice", officer_role="director")],
        total_results=1,
    )
    mock_client.get_pscs.return_value = CHPSCsResponse(
        items=[CHPSCItem(name="Alice", notified_on=date(2016, 4, 6))],
        total_results=1,
    )
    mock_client.get_charges.return_value = CHChargesResponse(
        items=[CHChargeItem(charge_code="0001", status="outstanding")],
        total_count=1,
    )

    with (
        patch(
            "app.tasks.ingestion.create_ch_client",
            return_value=_async_cm(mock_client),
        ),
        patch(
            "app.tasks.ingestion.get_session",
            return_value=_async_cm(mock_session),
        ),
        patch(
            "app.tasks.ingestion.upsert_company",
            new_callable=AsyncMock,
            return_value=company_id,
        ),
        patch("app.tasks.ingestion.upsert_filings", new_callable=AsyncMock, return_value=[uuid.uuid4()]),
        patch("app.tasks.ingestion.upsert_officers", new_callable=AsyncMock),
        patch("app.tasks.ingestion.upsert_pscs", new_callable=AsyncMock),
        patch("app.tasks.ingestion.upsert_charges", new_callable=AsyncMock),
    ):
        result = await _refresh_company_async("12345678")

    assert result["company_number"] == "12345678"
    assert result["filings"] == 1
    assert result["officers"] == 1
    assert result["pscs"] == 1
    assert result["charges"] == 1
    mock_session.commit.assert_called_once()


async def test_refresh_company_async_commits_once_on_success() -> None:
    """Commit is called exactly once at the end of a successful refresh."""
    company_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_client = AsyncMock()

    mock_client.get_company.return_value = _make_profile()
    mock_client.get_filing_history.return_value = CHFilingHistoryResponse(items=[], total_count=0)
    mock_client.get_officers.return_value = CHOfficersResponse(items=[], total_results=0)
    mock_client.get_pscs.return_value = CHPSCsResponse(items=[], total_results=0)
    mock_client.get_charges.return_value = CHChargesResponse(items=[], total_count=0)

    with (
        patch("app.tasks.ingestion.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.ingestion.get_session", return_value=_async_cm(mock_session)),
        patch("app.tasks.ingestion.upsert_company", new_callable=AsyncMock, return_value=company_id),
        patch("app.tasks.ingestion.upsert_filings", new_callable=AsyncMock, return_value=[]),
        patch("app.tasks.ingestion.upsert_officers", new_callable=AsyncMock),
        patch("app.tasks.ingestion.upsert_pscs", new_callable=AsyncMock),
        patch("app.tasks.ingestion.upsert_charges", new_callable=AsyncMock),
    ):
        await _refresh_company_async("12345678")

    mock_session.commit.assert_called_once()
    mock_session.rollback.assert_not_called()


# ---------------------------------------------------------------------------
# Sub-task async implementations
# ---------------------------------------------------------------------------


async def test_fetch_filings_raises_if_company_missing() -> None:
    """_fetch_filings_async raises ValueError when company not in DB."""
    mock_session = AsyncMock()
    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = missing_result

    mock_client = AsyncMock()

    with (
        patch("app.tasks.ingestion.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.ingestion.get_session", return_value=_async_cm(mock_session)),
    ):
        with pytest.raises(ValueError, match="not found in DB"):
            await _fetch_filings_async("00000000")


async def test_fetch_filings_commits_on_success() -> None:
    company_id = uuid.uuid4()
    mock_session = AsyncMock()
    found = MagicMock()
    found.scalar_one_or_none.return_value = company_id
    mock_session.execute.return_value = found

    mock_client = AsyncMock()
    mock_client.get_filing_history.return_value = CHFilingHistoryResponse(
        items=[CHFilingHistoryItem(transaction_id="TX1")], total_count=1
    )

    with (
        patch("app.tasks.ingestion.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.ingestion.get_session", return_value=_async_cm(mock_session)),
        patch("app.tasks.ingestion.upsert_filings", new_callable=AsyncMock, return_value=[uuid.uuid4()]),
    ):
        result = await _fetch_filings_async("12345678")

    assert result["filings"] == 1
    mock_session.commit.assert_called_once()


async def test_fetch_charges_uses_paginated_results() -> None:
    """Charges fetch follows paginated results correctly."""
    company_id = uuid.uuid4()
    mock_session = AsyncMock()
    found = MagicMock()
    found.scalar_one_or_none.return_value = company_id
    mock_session.execute.return_value = found

    mock_client = AsyncMock()
    mock_client.get_charges.return_value = CHChargesResponse(
        items=[
            CHChargeItem(charge_code="C001", status="outstanding"),
            CHChargeItem(charge_code="C002", status="satisfied"),
        ],
        total_count=2,
    )

    with (
        patch("app.tasks.ingestion.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.ingestion.get_session", return_value=_async_cm(mock_session)),
        patch("app.tasks.ingestion.upsert_charges", new_callable=AsyncMock),
    ):
        result = await _fetch_charges_async("12345678")

    assert result["charges"] == 2


# ---------------------------------------------------------------------------
# _paginate — None total_count guard
# ---------------------------------------------------------------------------


async def test_paginate_continues_when_total_is_none() -> None:
    """When total_attr is None, pagination is driven only by resp.items being non-empty."""
    items_p1 = [CHFilingHistoryItem(transaction_id=f"TX{i:03d}") for i in range(100)]
    items_p2 = [CHFilingHistoryItem(transaction_id="TX100")]
    items_p3: list[CHFilingHistoryItem] = []

    # total_count=None on all responses
    resp_p1 = CHFilingHistoryResponse(items=items_p1, total_count=None)
    resp_p2 = CHFilingHistoryResponse(items=items_p2, total_count=None)
    resp_p3 = CHFilingHistoryResponse(items=items_p3, total_count=None)

    mock_fn = AsyncMock(side_effect=[resp_p1, resp_p2, resp_p3])

    result = await _paginate(mock_fn, "12345678", total_attr="total_count")

    assert len(result) == 101
    assert mock_fn.call_count == 3  # stops only when items is empty


async def test_paginate_does_not_truncate_on_none_total_single_page() -> None:
    """A single-page result with total_count=None returns items and stops."""
    item = CHFilingHistoryItem(transaction_id="TX001")
    resp_with_items = CHFilingHistoryResponse(items=[item], total_count=None)
    resp_empty = CHFilingHistoryResponse(items=[], total_count=None)

    mock_fn = AsyncMock(side_effect=[resp_with_items, resp_empty])

    result = await _paginate(mock_fn, "12345678", total_attr="total_count")

    assert result == [item]
    assert mock_fn.call_count == 2


# ---------------------------------------------------------------------------
# refresh_run wiring
# ---------------------------------------------------------------------------


async def test_refresh_company_async_creates_and_finishes_run() -> None:
    """create_refresh_run is called once before work; finish_refresh_run called with 'completed'."""
    company_id = uuid.uuid4()
    run_id = uuid.uuid4()
    mock_session = AsyncMock()
    mock_client = AsyncMock()

    mock_client.get_company.return_value = _make_profile()
    mock_client.get_filing_history.return_value = CHFilingHistoryResponse(items=[], total_count=0)
    mock_client.get_officers.return_value = CHOfficersResponse(items=[], total_results=0)
    mock_client.get_pscs.return_value = CHPSCsResponse(items=[], total_results=0)
    mock_client.get_charges.return_value = CHChargesResponse(items=[], total_count=0)

    with (
        patch("app.tasks.ingestion.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.ingestion.get_session", return_value=_async_cm(mock_session)),
        patch("app.tasks.ingestion.upsert_company", new_callable=AsyncMock, return_value=company_id),
        patch("app.tasks.ingestion.upsert_filings", new_callable=AsyncMock, return_value=[]),
        patch("app.tasks.ingestion.upsert_officers", new_callable=AsyncMock),
        patch("app.tasks.ingestion.upsert_pscs", new_callable=AsyncMock),
        patch("app.tasks.ingestion.upsert_charges", new_callable=AsyncMock),
        patch("app.tasks.ingestion.create_refresh_run", new_callable=AsyncMock, return_value=run_id) as mock_create,
        patch("app.tasks.ingestion.finish_refresh_run", new_callable=AsyncMock) as mock_finish,
    ):
        await _refresh_company_async("12345678")

    mock_create.assert_called_once_with(None, "full")
    mock_finish.assert_called_once_with(run_id, "completed")


async def test_refresh_company_async_finishes_run_as_failed_on_error() -> None:
    """When an exception is raised, finish_refresh_run is called with 'failed'."""
    run_id = uuid.uuid4()
    mock_client = AsyncMock()
    mock_client.get_company.side_effect = RuntimeError("upstream down")

    with (
        patch("app.tasks.ingestion.create_ch_client", return_value=_async_cm(mock_client)),
        patch("app.tasks.ingestion.get_session", return_value=_async_cm(AsyncMock())),
        patch("app.tasks.ingestion.create_refresh_run", new_callable=AsyncMock, return_value=run_id),
        patch("app.tasks.ingestion.finish_refresh_run", new_callable=AsyncMock) as mock_finish,
    ):
        with pytest.raises(RuntimeError):
            await _refresh_company_async("12345678")

    mock_finish.assert_called_once()
    call_args = mock_finish.call_args
    assert call_args[0][0] == run_id
    assert call_args[0][1] == "failed"
    assert "upstream down" in call_args[1].get("error_summary", "")


# ---------------------------------------------------------------------------
# refresh_company Celery task — non-retryable exceptions
# ---------------------------------------------------------------------------


def test_refresh_company_does_not_retry_not_found() -> None:
    """CHNotFoundError must propagate without triggering self.retry()."""
    from app.tasks.ingestion import refresh_company

    mock_self = MagicMock()
    with (
        patch("asyncio.run", side_effect=CHNotFoundError("/company/00000000")),
    ):
        with pytest.raises(CHNotFoundError):
            refresh_company.__wrapped__(mock_self, "00000000")

    mock_self.retry.assert_not_called()


def test_refresh_company_does_not_retry_auth_error() -> None:
    """CHAuthError must propagate without triggering self.retry()."""
    from app.tasks.ingestion import refresh_company

    mock_self = MagicMock()
    with (
        patch("asyncio.run", side_effect=CHAuthError()),
    ):
        with pytest.raises(CHAuthError):
            refresh_company.__wrapped__(mock_self, "00000000")

    mock_self.retry.assert_not_called()
