"""
Public read endpoints for company intelligence.

All routes are mounted under /api/v1 (see main.py).

Endpoint overview:
  GET /search                                 — company search
  GET /companies/{company_number}             — company aggregate (snapshot-first)
  GET /companies/{company_number}/financials  — financial periods + derived metrics
  GET /companies/{company_number}/signals     — risk signals
  GET /companies/{company_number}/filings     — filing history (cursor-paginated)
  GET /companies/{company_number}/officers    — officer appointments
  GET /companies/{company_number}/psc         — persons with significant control
  GET /companies/{company_number}/charges     — registered charges

Snapshot vs. direct read strategy:
  - /companies/{number} uses the pre-built snapshot (snapshot_payload JSONB) for
    the AI summary and active-signals summary; company identity and overview fields
    are still read directly so they reflect the freshest available data.
  - All sub-resource endpoints query source tables directly — they provide
    the detailed, pageable views that the snapshot does not inline.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.queries.companies import (
    address_snippet,
    get_charges,
    get_company_by_number,
    get_current_snapshot,
    get_derived_metrics_for_period,
    get_facts_for_period,
    get_filings,
    get_financial_periods,
    get_officers,
    get_psc_records,
    get_risk_signals,
    search_companies,
)
from app.schemas.common import bad_request, not_found, ok, ok_list
from app.schemas.company import (
    ActiveSignalSummary,
    AiNarrativeSummary,
    CompanyAggregate,
    CompanyCore,
    CompanyOverview,
    FinancialSummary,
    Freshness,
    KeyObservation,
    NarrativeParagraph,
    SearchResultItem,
)
from app.schemas.filing import (
    ChargeItem,
    FilingItem,
    OfficerItem,
    PscItem,
    SignalItem,
)
from app.schemas.financial import (
    FactDetail,
    FinancialsResponse,
    MetricDetail,
    PeriodFacts,
    SeriesPoint,
    confidence_band,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Dependency alias
# ---------------------------------------------------------------------------

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------


@router.get("/search")
async def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    status: str | None = None,
) -> JSONResponse:
    """
    Search companies by name (partial match) or exact company number.

    Returns results ordered: exact number match first, then name matches
    sorted alphabetically.
    """
    rows = await search_companies(session, q, limit=limit, status=status)

    items = []
    for r in rows:
        addr = r.get("registered_office_address")
        match_type = "exact_number" if r.get("company_number") == q.strip() else "name"
        items.append(
            SearchResultItem(
                company_number=r["company_number"],
                company_name=r["company_name"],
                company_status=r.get("company_status"),
                company_type=r.get("company_type"),
                date_of_creation=r.get("date_of_creation"),
                registered_office_address_snippet=address_snippet(addr),
                sic_codes=r.get("sic_codes") or [],
                match_type=match_type,
            ).model_dump(mode="json")
        )

    return JSONResponse(ok_list(items, limit=limit))


# ---------------------------------------------------------------------------
# GET /companies/{company_number}  — aggregate view
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}")
async def get_company(
    company_number: str,
    session: SessionDep,
) -> JSONResponse:
    """
    Aggregate company view.

    Returns company identity, compliance overview, financial summary,
    active risk signals, AI/template narrative, and freshness metadata
    in a single response designed to power the main company page.
    """
    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]

    # ---- company core + overview ----
    company = CompanyCore(
        company_number=row["company_number"],
        company_name=row["company_name"],
        company_status=row.get("company_status"),
        company_type=row.get("company_type"),
        subtype=row.get("subtype"),
        jurisdiction=row.get("jurisdiction"),
        date_of_creation=row.get("date_of_creation"),
        cessation_date=row.get("cessation_date"),
        has_insolvency_history=row.get("has_insolvency_history"),
        has_charges=row.get("has_charges"),
        sic_codes=row.get("sic_codes") or [],
        registered_office_address=row.get("registered_office_address"),
    )
    overview = CompanyOverview(
        accounts_next_due=row.get("accounts_next_due"),
        accounts_overdue=row.get("accounts_overdue"),
        confirmation_statement_next_due=row.get("confirmation_statement_next_due"),
        confirmation_statement_overdue=row.get("confirmation_statement_overdue"),
    )

    # ---- snapshot (AI summary, active signals, financial summary) ----
    snapshot = await get_current_snapshot(session, company_id)
    payload: dict = snapshot["snapshot_payload"] if snapshot else {}

    ai_summary: AiNarrativeSummary | None = None
    active_signals: list[ActiveSignalSummary] = []
    financial_summary: FinancialSummary | None = None

    if payload:
        # AI / template narrative
        ai_raw = payload.get("ai_summary")
        if ai_raw:
            ai_summary = AiNarrativeSummary(
                summary_short=ai_raw.get("summary_short", ""),
                narrative_paragraphs=[
                    NarrativeParagraph(**p)
                    for p in ai_raw.get("narrative_paragraphs", [])
                ],
                key_observations=[
                    KeyObservation(**o)
                    for o in ai_raw.get("key_observations", [])
                ],
                data_quality_note=ai_raw.get("data_quality_note"),
                caveats=ai_raw.get("caveats", []),
                source=payload.get("summary_source", "template"),
            )

        # Active signals — fired/active only, summary form
        for sig in payload.get("active_signals", []):
            active_signals.append(
                ActiveSignalSummary(
                    signal_code=sig["signal_code"],
                    signal_name=sig["signal_name"],
                    category=sig["category"],
                    severity=sig["severity"],
                    explanation=sig["explanation"],
                )
            )

        # Financial summary
        fin = payload.get("financial_summary")
        if fin:
            band = fin.get("confidence_band") or confidence_band(fin.get("confidence"))
            financial_summary = FinancialSummary(
                latest_period_end=fin.get("latest_period_end"),
                period_start=fin.get("period_start"),
                accounts_type=fin.get("accounts_type"),
                currency_code=fin.get("currency_code"),
                confidence=fin.get("confidence"),
                confidence_band=band,
                revenue=fin.get("revenue"),
                net_assets_liabilities=fin.get("net_assets_liabilities"),
                profit_loss_after_tax=fin.get("profit_loss_after_tax"),
                average_number_of_employees=fin.get("average_number_of_employees"),
            )

    # ---- freshness ----
    freshness = Freshness(
        snapshot_generated_at=snapshot["snapshot_generated_at"] if snapshot else None,
        source_last_checked_at=(
            snapshot["source_last_checked_at"]
            if snapshot
            else row.get("source_last_checked_at")
        ),
        freshness_status=snapshot["freshness_status"] if snapshot else "unknown",
        snapshot_status="current" if snapshot else "not_built",
        methodology_version=snapshot["methodology_version"] if snapshot else None,
    )

    aggregate = CompanyAggregate(
        company=company,
        overview=overview,
        financial_summary=financial_summary,
        active_signals=active_signals,
        ai_summary=ai_summary,
        freshness=freshness,
    )

    return JSONResponse(ok(aggregate.model_dump(mode="json")))


# ---------------------------------------------------------------------------
# GET /companies/{company_number}/financials
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}/financials")
async def get_financials(
    company_number: str,
    session: SessionDep,
    num_periods: Annotated[int, Query(ge=1, le=10)] = 5,
) -> JSONResponse:
    """
    Financial periods, extracted facts, derived metrics, and time series.

    Returns up to num_periods non-restated periods (newest first).
    Derived metrics are computed for the most recent (primary) period only.
    """
    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]
    periods_raw = await get_financial_periods(session, company_id, num_periods=num_periods)

    if not periods_raw:
        # Known company, no financial data extracted yet
        return JSONResponse(
            ok(
                FinancialsResponse(
                    data_quality={"message": "No financial periods available"}
                ).model_dump(mode="json")
            )
        )

    # ---- build PeriodFacts list ----
    periods: list[PeriodFacts] = []
    for p in periods_raw:
        facts_raw = await get_facts_for_period(session, p["id"])
        facts: dict[str, FactDetail] = {}
        for f in facts_raw:
            facts[f["fact_name"]] = FactDetail(
                value=f.get("fact_value"),
                unit=f.get("unit"),
                confidence=f.get("extraction_confidence"),
                confidence_band=confidence_band(f.get("extraction_confidence")),
                raw_label=f.get("raw_label"),
                extraction_method=f.get("extraction_method"),
                is_derived=bool(f.get("is_derived")),
            )
        band = confidence_band(p.get("extraction_confidence"))
        periods.append(
            PeriodFacts(
                period_id=p["id"],
                period_end=p["period_end"],
                period_start=p.get("period_start"),
                accounts_type=p.get("accounts_type"),
                currency_code=p.get("currency_code"),
                extraction_confidence=p.get("extraction_confidence"),
                confidence_band=band,
                facts=facts,
            )
        )

    # ---- derived metrics for primary (most recent) period ----
    primary = periods_raw[0]
    metrics_raw = await get_derived_metrics_for_period(
        session, company_id, primary["id"]
    )
    derived_metrics: dict[str, MetricDetail] = {}
    for m in metrics_raw:
        band = m.get("confidence_band") or confidence_band(m.get("confidence"))
        derived_metrics[m["metric_key"]] = MetricDetail(
            value=m.get("metric_value"),
            unit=m.get("unit") or "ratio",
            confidence=m.get("confidence"),
            confidence_band=band,
            warnings=m.get("warnings") or [],
        )

    # ---- time series per fact (for charting) ----
    all_fact_names: set[str] = set()
    for p in periods:
        all_fact_names.update(p.facts.keys())

    series: dict[str, list[SeriesPoint]] = {}
    for fact_name in sorted(all_fact_names):
        points: list[SeriesPoint] = []
        for p in periods:
            fd = p.facts.get(fact_name)
            points.append(
                SeriesPoint(
                    period_end=p.period_end,
                    value=fd.value if fd else None,
                    confidence_band=fd.confidence_band if fd else "unavailable",
                )
            )
        series[fact_name] = points

    # ---- data quality summary ----
    available_facts = sum(
        1
        for p in periods[:1]  # primary period only
        for fd in p.facts.values()
        if fd.value is not None
    )
    data_quality = {
        "periods_available": len(periods),
        "primary_period_facts_available": available_facts,
        "primary_period_confidence_band": periods[0].confidence_band,
    }

    return JSONResponse(
        ok(
            FinancialsResponse(
                periods=periods,
                derived_metrics=derived_metrics,
                series=series,
                data_quality=data_quality,
            ).model_dump(mode="json")
        )
    )


# ---------------------------------------------------------------------------
# GET /companies/{company_number}/signals
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}/signals")
async def get_signals(
    company_number: str,
    session: SessionDep,
    status: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """
    Risk signals for a company.

    status: "active" | "resolved" | "all" (default all).
    """
    if status and status not in ("active", "resolved", "all"):
        return JSONResponse(
            bad_request("status must be 'active', 'resolved', or 'all'"),
            status_code=400,
        )

    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]
    signals_raw = await get_risk_signals(session, company_id, status=status)

    items = [
        SignalItem(
            signal_code=s["signal_code"],
            signal_name=s["signal_name"],
            category=s["category"],
            severity=s["severity"],
            status=s["status"],
            explanation=s["explanation"],
            evidence=s.get("evidence"),
            methodology_version=s["methodology_version"],
            first_detected_at=s["first_detected_at"],
            last_confirmed_at=s["last_confirmed_at"],
            resolved_at=s.get("resolved_at"),
        ).model_dump(mode="json")
        for s in signals_raw
    ]

    return JSONResponse(ok_list(items))


# ---------------------------------------------------------------------------
# GET /companies/{company_number}/filings
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}/filings")
async def get_company_filings(
    company_number: str,
    session: SessionDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    category: str | None = None,
) -> JSONResponse:
    """
    Filing history for a company (newest first, cursor-paginated).

    cursor: opaque pagination token from the previous response's
            meta.pagination.next_cursor field.
    category: optional filter (e.g. "accounts", "confirmation-statement").
    """
    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]
    filings_raw, next_cursor = await get_filings(
        session, company_id, cursor=cursor, limit=limit, category=category
    )

    items = [
        FilingItem(
            transaction_id=f["transaction_id"],
            category=f.get("category"),
            type=f.get("type"),
            description=f.get("description"),
            action_date=f.get("action_date"),
            date_filed=f.get("date_filed"),
            pages=f.get("pages"),
            paper_filed=f.get("paper_filed"),
            has_document=bool(f.get("has_document")),
            parse_status=f.get("parse_status"),
            source_links=f.get("source_links"),
        ).model_dump(mode="json")
        for f in filings_raw
    ]

    return JSONResponse(ok_list(items, next_cursor=next_cursor, limit=limit))


# ---------------------------------------------------------------------------
# GET /companies/{company_number}/officers
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}/officers")
async def get_company_officers(
    company_number: str,
    session: SessionDep,
    status: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """
    Officer appointments for a company.

    status: "active" (current only) | "resigned" | "all" (default all).
    """
    if status and status not in ("active", "resigned", "all"):
        return JSONResponse(
            bad_request("status must be 'active', 'resigned', or 'all'"),
            status_code=400,
        )

    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]
    officers_raw = await get_officers(session, company_id, status=status)

    items = [
        OfficerItem(
            name=o["name"],
            role=o.get("role"),
            nationality=o.get("nationality"),
            occupation=o.get("occupation"),
            country_of_residence=o.get("country_of_residence"),
            appointed_on=o.get("appointed_on"),
            resigned_on=o.get("resigned_on"),
            is_current=bool(o.get("is_current")),
            date_of_birth_month=o.get("date_of_birth_month"),
            date_of_birth_year=o.get("date_of_birth_year"),
        ).model_dump(mode="json")
        for o in officers_raw
    ]

    return JSONResponse(ok_list(items))


# ---------------------------------------------------------------------------
# GET /companies/{company_number}/psc
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}/psc")
async def get_company_psc(
    company_number: str,
    session: SessionDep,
    status: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """
    Persons with significant control (PSC) records for a company.

    status: "active" (current only) | "ceased" | "all" (default all).
    """
    if status and status not in ("active", "ceased", "all"):
        return JSONResponse(
            bad_request("status must be 'active', 'ceased', or 'all'"),
            status_code=400,
        )

    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]
    psc_raw = await get_psc_records(session, company_id, status=status)

    items = [
        PscItem(
            name=p.get("name"),
            kind=p.get("kind"),
            natures_of_control=p.get("natures_of_control") or [],
            notified_on=p.get("notified_on"),
            ceased_on=p.get("ceased_on"),
            nationality=p.get("nationality"),
            country_of_residence=p.get("country_of_residence"),
            is_current=bool(p.get("is_current")),
            date_of_birth_month=p.get("date_of_birth_month"),
            date_of_birth_year=p.get("date_of_birth_year"),
        ).model_dump(mode="json")
        for p in psc_raw
    ]

    return JSONResponse(ok_list(items))


# ---------------------------------------------------------------------------
# GET /companies/{company_number}/charges
# ---------------------------------------------------------------------------


@router.get("/companies/{company_number}/charges")
async def get_company_charges(
    company_number: str,
    session: SessionDep,
    status: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """
    Registered charges for a company.

    status: "outstanding" | "satisfied" | "all" (default all).
    """
    if status and status not in ("outstanding", "satisfied", "all"):
        return JSONResponse(
            bad_request("status must be 'outstanding', 'satisfied', or 'all'"),
            status_code=400,
        )

    row = await get_company_by_number(session, company_number)
    if not row:
        return JSONResponse(
            not_found(f"Company {company_number!r} not found"),
            status_code=404,
        )

    company_id: uuid.UUID = row["id"]
    charges_raw = await get_charges(session, company_id, status=status)

    items = [
        ChargeItem(
            charge_id=c["charge_id"],
            status=c.get("status"),
            delivered_on=c.get("delivered_on"),
            created_on=c.get("created_on"),
            resolved_on=c.get("resolved_on"),
            persons_entitled=c.get("persons_entitled"),
            particulars=c.get("particulars"),
            source_last_checked_at=c.get("source_last_checked_at"),
        ).model_dump(mode="json")
        for c in charges_raw
    ]

    return JSONResponse(ok_list(items))
