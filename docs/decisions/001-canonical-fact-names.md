# Decision 001 — Canonical Financial Fact Names

**Status:** RESOLVED — Option B adopted (docs/05 names). See decision below.
**Resolved:** Phase 1B (2026-03-17)

All blocked items are now unblocked. Proceed with implementation.

---

**Original blocker — must be resolved before any of the following are implemented:**
- SQLAlchemy `financial_facts` model
- Alembic migration for `financial_facts` and `financial_periods`
- Parser canonical mapping table (`docs/05-parser-design.md §Mapping layer`)
- API financial facts serializer
- Any test fixture that references canonical fact names

**Raised:** Phase 0
**Owner:** To be decided before Phase 1 domain model implementation

---

## Context

Two specification documents define the canonical financial fact names used by the `financial_facts` table and the parser pipeline. They use different naming conventions for the same accounting concepts.

---

## Naming conflicts

| Accounting concept | `docs/02-database-schema.md` | `docs/05-parser-design.md` |
|---|---|---|
| Operating profit or loss | `operating_profit` | `operating_profit_loss` |
| Profit or loss after tax | `profit_after_tax` | `profit_loss_after_tax` |
| Net assets or liabilities | `net_assets` | `net_assets_liabilities` |
| Cash at bank | `cash_at_bank` | `cash_bank_on_hand` |
| Average employees | `average_employees` | `average_number_of_employees` |

Names that agree across both documents (no conflict):
- `revenue`
- `gross_profit`
- `current_assets`
- `fixed_assets`
- `total_assets_less_current_liabilities`
- `creditors_due_within_one_year`
- `creditors_due_after_one_year`

---

## Options

### Option A — Use docs/02 names (shorter)
- **Pro:** Matches the database schema document as written; shorter column names
- **Con:** `operating_profit` and `profit_after_tax` do not express sign direction; less aligned with XBRL taxonomy label conventions used in iXBRL filings; diverges from the parser spec before a single line of parser code is written

### Option B — Use docs/05 names (more explicit)
- **Pro:** `operating_profit_loss` and `profit_loss_after_tax` express that the value may be positive or negative — important for a product that must never silently convert missing or negative values; closer to XBRL taxonomy label conventions (`uk-gaap:ProfitLossForPeriod`, etc.); parser and schema share one vocabulary
- **Con:** Longer column names; requires updating docs/02 to match

### Option C — Define a third canonical set
- **Not recommended:** creates a third point of divergence; any future contributor would face three different namings to reconcile

---

## Decision (Phase 1B — FINAL)

**Option B adopted: use docs/05 names throughout.**

Docs updated:
- `docs/02-database-schema.md` — recommended `fact_name` values updated to docs/05 names
- `docs/03-api-spec.md` — financials example updated (`net_assets` → `net_assets_liabilities`)

Rationale:
1. **Parser is the origin.** The parser canonical map (docs/05) is the first code to assign these names. Making the database match the parser eliminates a rename at the persistence boundary.
2. **Sign direction.** `operating_profit_loss`, `profit_loss_after_tax`, and `net_assets_liabilities` explicitly communicate that values may be negative. `operating_profit` and `net_assets` read as strictly positive, which is factually wrong for companies with losses or liabilities exceeding assets.
3. **XBRL alignment.** docs/05 names are closer to UK GAAP XBRL taxonomy elements (e.g. `uk-gaap:CashAtBankAndInHand`, `uk-gaap:NetAssetsLiabilities`), reducing mapping complexity when iXBRL parsing is implemented.
4. **API stability.** `fact_name` values surface directly as keys in the financials response (docs/03 §8). Sign-explicit names prevent consumer confusion when a value is negative.

---

## Canonical fact names (FINAL)

| Concept | **Canonical name (adopted)** |
|---------|------------------------------|
| Revenue | `revenue` |
| Gross profit | `gross_profit` |
| Operating profit or loss | `operating_profit_loss` |
| Profit or loss after tax | `profit_loss_after_tax` |
| Current assets | `current_assets` |
| Fixed assets | `fixed_assets` |
| Total assets less current liabilities | `total_assets_less_current_liabilities` |
| Creditors due within one year | `creditors_due_within_one_year` |
| Creditors due after one year | `creditors_due_after_one_year` |
| Net assets or liabilities | `net_assets_liabilities` |
| Cash at bank and in hand | `cash_bank_on_hand` |
| Average number of employees | `average_number_of_employees` |

---

## Previously blocked — now unblocked

- [x] `apps/api/app/models/financial_fact.py` — implemented Phase 1B
- [x] `apps/api/app/models/financial_period.py` — implemented Phase 1B
- [x] Alembic migration: `financial_periods` table — 0002_financial_domain.py
- [x] Alembic migration: `financial_facts` table — 0002_financial_domain.py
- [ ] `apps/worker/app/parsers/canonical_map.py` — deferred to parser phase
- [ ] `apps/api/app/schemas/financials.py` — deferred to API router phase
- [ ] Any parser fixture or golden test file referencing fact names — deferred to parser phase
