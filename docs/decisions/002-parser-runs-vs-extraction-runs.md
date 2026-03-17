# Decision 002: parser_runs vs extraction_runs

**Status:** RESOLVED — extraction_runs adopted (docs/02 authoritative)
**Date:** 2026-03-17
**Relates to:** docs/02-database-schema.md §14, docs/05-parser-design.md §6

---

## Conflict

Two naming conventions appear across the documentation for the same concept:

| Source    | Table name            | Notes                                        |
|-----------|-----------------------|----------------------------------------------|
| docs/02   | `extraction_runs`     | Schema specification; also has confidence col |
| docs/05   | `parser_runs`         | Parser design doc; also has `parser_run_events` |

docs/05 additionally specifies a `parser_run_events` table (individual document processing events within a run), which has no equivalent in docs/02.

---

## Analysis

docs/02 is the canonical database schema spec — it defines the PostgreSQL table layout that Alembic migrations follow. docs/05 describes the parser pipeline design and uses different naming informally.

The `confidence` column on `extraction_runs` (docs/02, type `NUMERIC(5,4)`) is a concrete schema detail that must live somewhere. There is no meaningful distinction between "extraction run" and "parser run" at the data level — both describe a single invocation of the document parsing pipeline for one filing document.

docs/05's `parser_run_events` concept (per-document event log within a run) may be useful operationally but is absent from the schema spec. Adding it would be an extension, not a conflict resolution.

---

## Decision

**Adopt docs/02 naming: `extraction_runs`.**

Rationale:
- docs/02 is the schema source of truth (CLAUDE.md: "favour the docs unless a strong technical reason requires an update")
- The migration (0001_initial_schema.py) and ORM model (ops.py) already use `extraction_runs`
- The `confidence` field is best placed on `extraction_runs` per docs/02

**`parser_run_events` status:** Deferred. Not implemented in Phase 1A. If needed, it should be added as a new table (linked to `extraction_runs.id`) in a future phase, with a docs/02 update.

---

## Impact

- ORM model: `apps/api/app/models/ops.py` — `ExtractionRun` (not `ParserRun`)
- Migration: `0001_initial_schema.py` — `extraction_runs` table
- All future code referencing parser pipeline runs must use `extraction_run_id` as the FK column name

---

## Open question

docs/05 §6 describes per-document events that may be useful for observability (e.g. which page of a PDF caused a parse error). If this is needed, open a new decision record before adding the table.
