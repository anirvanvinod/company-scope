"""
Model registry — imports all ORM models so they are registered with
Base.metadata before Alembic autogenerate or create_all() is called.

Import order follows the FK dependency chain to avoid forward-reference
issues during metadata introspection.
"""

from app.models.methodology import MethodologyVersion
from app.models.user import User, Watchlist, WatchlistItem
from app.models.company import Company, CompanySnapshot
from app.models.filing import Filing, FilingDocument
from app.models.officer import Officer, OfficerAppointment
from app.models.psc import PscRecord
from app.models.charge import Charge
from app.models.insolvency import InsolvencyCase
from app.models.financial_period import FinancialPeriod
from app.models.financial_fact import FinancialFact
from app.models.signal import RiskSignal
from app.models.ops import RefreshRun, ExtractionRun
from app.models.audit import AuditEvent

__all__ = [
    "MethodologyVersion",
    "User",
    "Watchlist",
    "WatchlistItem",
    "Company",
    "CompanySnapshot",
    "Filing",
    "FilingDocument",
    "Officer",
    "OfficerAppointment",
    "PscRecord",
    "Charge",
    "InsolvencyCase",
    "FinancialPeriod",
    "FinancialFact",
    "RiskSignal",
    "RefreshRun",
    "ExtractionRun",
    "AuditEvent",
]
