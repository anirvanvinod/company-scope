# Decision 003: Restated Financial Period Strategy

**Status:** RESOLVED — Option B adopted (add `is_restated` to unique constraint key)
**Date:** 2026-03-17
**Relates to:** docs/02-database-schema.md §10 financial_periods, docs/05-parser-design.md §Period handling

---

## Problem

`financial_periods` has a unique constraint on `(company_id, period_end, accounts_type)`.

`is_restated` is a column on the same table but is not part of the unique key. If a restated
accounts filing arrives for a period already stored with the same `(company_id, period_end,
accounts_type)` values, the database would reject the insert with a unique constraint violation.

The parser must be able to store both the original and the restated period without destroying
the original, per docs/05: *"Never overwrite prior facts without versioning or supersession logic."*

---

## Options evaluated

### Option A — Update original row in place
Set `is_restated=True` on the existing row and update its facts.

**Rejected.** Destroys the original extracted values. Violates docs/05 non-overwrite rule and
the general provenance principle. Cannot be audited or reversed.

### Option B — Add `is_restated` to the unique constraint key ✓ ADOPTED
Constraint becomes: `UNIQUE (company_id, period_end, accounts_type, is_restated)`.

Allows exactly one original (`is_restated=False`) and one restated (`is_restated=True`) row
per `(company_id, period_end, accounts_type)` triple. Both rows survive. The UI and signals
layer queries the most recent or the restated version depending on context.

**Chosen for MVP.** Satisfies the non-overwrite rule. One migration, no new columns. Handles
the real-world case (one restatement per period) without added model complexity.

**Known limitation:** If a period is restated more than once (rare), a second restated row
would collide with the first. If this becomes a real problem, escalate to Option C.

### Option C — Supersession FK (`supersedes_period_id`)
Add `supersedes_period_id UUID REFERENCES financial_periods(id)` to `financial_periods`.
Each restatement points to the period it supersedes. The "active" period is the one with
no record pointing to it.

**Deferred.** Architecturally correct for multi-restatement cases and provides a full audit
chain. Added complexity before any restatement is encountered. Should be revisited if the
parser phase reveals multiple restatements per period in practice.

---

## Decision

**Option B.** Add `is_restated` to the unique constraint on `financial_periods`.

### Schema change

```sql
-- Drop existing constraint
ALTER TABLE financial_periods DROP CONSTRAINT uq_financial_periods;

-- Add new constraint including is_restated
ALTER TABLE financial_periods
  ADD CONSTRAINT uq_financial_periods
  UNIQUE (company_id, period_end, accounts_type, is_restated);
```

Implemented in: `apps/api/alembic/versions/0003_restatement_constraint.py`
Model updated in: `apps/api/app/models/financial_period.py`

---

## Parser implications

When persisting a financial period the parser should:

1. Attempt to fetch an existing `(company_id, period_end, accounts_type, is_restated=False)` row.
2. If the incoming data is a restatement of an already-stored original:
   - Do NOT update the original row.
   - Insert a new row with `is_restated=True`.
3. If inserting a first-time original: `is_restated=False`.
4. If inserting a first-time restated filing (no original stored yet): `is_restated=True` is still
   correct — the constraint does not require an original to exist first.

---

## Open question (deferred)

- How should the API and signals layer decide which period version to use when both exist?
  Provisional answer: prefer the restated version (`is_restated=True`) when available.
  Formalise this as a query rule when the financials API router is implemented.
