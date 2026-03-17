# Testing Strategy

## Purpose
This document defines the testing approach for CompanyScope across frontend, backend, parser, infrastructure, and data quality layers.

The strategy is designed to support a public-data product where correctness, explainability, and graceful degradation matter more than superficial feature velocity.

## Testing goals
- prevent regressions in core company search and company profile flows
- ensure API contracts remain stable
- verify parser behaviour across representative filing formats
- guarantee traceability and confidence handling
- ensure missing or partial data does not produce misleading outputs
- support safe iteration as parser logic evolves

## Quality principles
- test the highest-risk paths first
- prefer deterministic tests for parsing and derived metrics
- explicitly test incomplete and malformed source data
- treat explainability and provenance as testable requirements
- use layered testing, not only end-to-end tests

## Test pyramid

### Unit tests
Fast, isolated tests for:
- utility functions
- signal rules
- metric calculations
- mapping functions
- validators
- API serializers

### Integration tests
Focused tests across component boundaries:
- API plus database
- worker plus storage
- parser plus persistence
- auth plus protected routes

### End-to-end tests
Full user workflows:
- search for company
- open company page
- inspect financials
- add to watchlist
- review filings and signals

### Data quality tests
Special layer for:
- canonical fact consistency
- confidence band correctness
- source traceability completeness
- stale data handling

## Recommended tools

### Frontend
- Vitest
- React Testing Library
- Playwright

### Backend
- Pytest
- httpx test client
- pytest-asyncio where required

### Database
- migration tests with Alembic
- isolated Postgres test database
- fixture-based seed data

### Parser
- Pytest snapshot tests
- golden file fixtures
- deterministic parser-run output comparisons

### Contract testing
- OpenAPI schema validation
- JSON schema response assertions
- typed client generation smoke tests

## Test environments

### Local
- Docker Compose
- seeded test Postgres
- local Redis
- MinIO for object storage tests

### CI
- ephemeral containers
- migration run before test suite
- parallel frontend/backend jobs
- cached dependencies

### Staging
- production-like environment
- limited real external API calls
- synthetic watchlist and refresh jobs

## Scope by layer

## 1. Frontend testing

### Component tests
Test:
- search input and autocomplete behaviour
- result list rendering
- company header cards
- confidence and severity badges
- empty states
- skeleton loading states
- methodology links

### Page tests
Test:
- search results page with mocked API
- company overview page with full data
- company overview with partial data
- financials tab with unavailable metrics
- filings tab filters
- watchlist interactions

### Accessibility tests
Verify:
- keyboard navigation
- focus states
- semantic tables
- chart data fallback tables
- screen-reader labels on badges and alerts

## 2. Backend API testing

### Search endpoints
Test:
- valid name query
- valid company number query
- empty query rejection
- rate-limited upstream fallback handling
- cached result behaviour

### Company aggregate endpoints
Test:
- fully hydrated company
- partially hydrated company
- stale cache with refresh trigger
- not found company
- upstream failure but cached fallback

### Auth endpoints
Test:
- sign-in flow
- protected watchlist endpoints
- invalid session rejection

### Error contract testing
Ensure every error response includes:
- consistent status code
- machine-readable error code
- human-readable message
- retryability where relevant

## 3. Parser testing

### Parser fixture strategy
Maintain a fixture library of representative documents:
- micro-entity accounts
- small company accounts
- dormant accounts
- structured iXBRL examples
- HTML semi-structured examples
- unsupported or malformed documents
- amended or restated examples

### Golden tests
For each fixture:
- parse output should match approved expected facts
- confidence bands should match expectations
- validation warnings should match expectations
- parser version changes should be intentional

### Mapping tests
Verify:
- raw labels map to expected canonical names
- synonyms do not create duplicate facts
- unsupported labels are preserved, not discarded silently

### Period tests
Verify:
- period end extraction
- current vs comparative distinction
- restatement handling
- null start date logic where appropriate

### Negative tests
Test:
- empty documents
- broken HTML
- unexpected namespaces
- mixed currency notation
- bracketed negatives
- scale annotation errors

## 4. Derived metrics and signal tests

### Metric tests
For each metric formula:
- normal case
- divide-by-zero case
- missing denominator
- negative values
- low-confidence source fact propagation

### Signal rule tests
Each rule must have:
- triggering example
- non-triggering example
- borderline threshold example
- missing evidence example

### Examples
- overdue accounts should trigger high severity
- negative net assets should trigger only when confidence threshold is met
- officer churn should use a defined rolling window
- confidence warnings should not be mixed into business risk counts incorrectly

## 5. Database and migration testing

### Migration tests
Every migration should be tested for:
- forward apply
- rollback where feasible
- compatibility with seeded fixtures
- index creation
- constraint correctness

### Data integrity tests
Verify:
- company_number uniqueness where intended
- foreign key relationships
- fact provenance references
- parser_run linkage
- risk signal methodology version linkage

## 6. Queue and worker testing

### Worker tests
Test:
- successful company ingest job
- document fetch retry
- parser retry behaviour
- dead-letter handling
- idempotent reprocessing

### Scheduling tests
Test:
- daily refresh picks correct records
- watchlist priority queue behaviour
- stale company selection logic
- duplicate job suppression

## 7. Observability testing

### Logging tests
Verify structured logs include:
- request id
- company number where relevant
- filing id where relevant
- parser version on parse jobs
- error class and stage

### Metrics tests
Verify instrumentation emits:
- request latency
- cache hits and misses
- parser success rate
- upstream API failure counts
- queue depth

## 8. Security testing

### Application security tests
Verify:
- Companies House API key never appears client-side
- protected endpoints reject unauthenticated access
- input validation blocks malformed queries
- rate limiting applies to public search endpoints
- SSR pages do not leak internal-only fields

### Secrets handling
Test:
- startup fails cleanly if required secrets are missing
- secret values are not logged
- configuration validation rejects invalid secret formats

## 9. Performance testing

### Search performance
Targets:
- cached search response under target threshold
- search UI remains responsive under rapid typing
- no duplicate upstream calls for equivalent debounced queries

### Company page performance
Targets:
- cached company page fast path
- partial render before secondary panels complete
- large filing timelines paginate correctly

### Parser performance
Measure:
- average document parse duration by format
- memory usage on larger filings
- queue throughput under batch refresh

## 10. End-to-end scenarios

### Scenario A: successful search and analysis
1. user searches for company
2. autocomplete returns results
3. user opens company page
4. overview loads
5. financials tab displays latest facts and trends
6. filings tab shows linked filings
7. watchlist add succeeds

### Scenario B: partial financial coverage
1. user opens company with limited structured filings
2. profile loads
3. financial chart shows partial series
4. confidence warning is visible
5. no fake zero values appear

### Scenario C: unsupported document
1. ingest pipeline encounters unsupported account document
2. company page still loads governance and filing data
3. financial section shows unavailable state
4. parser status indicates unsupported
5. no misleading metrics are shown

### Scenario D: stale cache fallback
1. upstream dependency fails
2. cached aggregate exists
3. page displays cached data with freshness notice
4. user can retry refresh later

## 11. Test data management

### Principles
- never rely entirely on live external APIs in CI
- use fixtures and mocks for determinism
- keep a small set of approved representative documents
- version fixtures when parser behaviour changes intentionally

### Recommended test data categories
- happy path data
- sparse data
- malformed data
- edge-case financial labels
- multiple officer changes
- charge-heavy company
- dormant company
- dissolved company

## 12. Release gates

A release should not ship unless:
- migrations pass
- unit and integration tests pass
- contract tests pass
- parser golden tests pass
- critical end-to-end flows pass
- no severe accessibility regressions are detected
- no secret leakage or major security test failures occur

## 13. Ownership
Suggested ownership split:
- frontend tests: web team
- backend contract and service tests: API team
- parser fixture and golden tests: data/parsing team
- end-to-end and release gates: shared responsibility
- methodology and signal approval tests: product plus engineering

## 14. MVP priority test suite
Implement first:
1. search API tests
2. company aggregate API tests
3. parser golden tests for a small fixture library
4. risk signal rule tests
5. Playwright happy path for search to company page
6. watchlist auth and add/remove tests
7. migration smoke tests

## 15. Deferred testing enhancements
Later add:
- property-based tests for parser inputs
- mutation testing for critical rule logic
- load tests for batch refresh jobs
- visual regression tests for dashboards
- chaos testing for upstream dependency failures
