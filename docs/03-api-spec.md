# CompanyScope API Specification

## Purpose
This document defines the internal and public-facing API surface for CompanyScope.

The API is designed for:
- fast search
- stable company profile retrieval
- transparent financial and risk analysis
- watchlists and alerts
- internal ingestion and maintenance workflows

## API style
- REST over HTTPS
- JSON request and response bodies
- OpenAPI-generated schema
- versioned path prefix
- typed validation on every input and response

## Base path
```text
/api/v1
```

## Auth strategy
### Public read endpoints
No auth required for:
- search
- company profile pages
- public methodology pages

### Authenticated endpoints
Required for:
- watchlists
- alerts
- saved comparisons
- manual refresh requests above public limits
- admin and internal endpoints

### Internal endpoints
Restricted to trusted service accounts or internal networks.

## Common response envelope
Use a lightweight envelope for consistency.

```json
{
  "data": {},
  "meta": {
    "request_id": "req_123",
    "generated_at": "2026-03-17T10:00:00Z"
  },
  "error": null
}
```

For list endpoints:
```json
{
  "data": [],
  "meta": {
    "request_id": "req_123",
    "pagination": {
      "next_cursor": null,
      "limit": 20
    }
  },
  "error": null
}
```

## Error shape
```json
{
  "data": null,
  "meta": {
    "request_id": "req_123"
  },
  "error": {
    "code": "validation_error",
    "message": "Invalid company number",
    "details": {}
  }
}
```

## Public endpoints

## 1. Search companies
### GET /api/v1/search
Search companies by name or exact company number.

#### Query params
- `q` string, required
- `limit` integer, optional, default 10, max 25
- `status` optional filter
- `exact_number_first` boolean, optional, default true

#### Example request
```http
GET /api/v1/search?q=tesco&limit=10
```

#### Example response
```json
{
  "data": [
    {
      "company_number": "00445790",
      "company_name": "TESCO PLC",
      "company_status": "active",
      "company_type": "plc",
      "date_of_creation": "1947-11-27",
      "registered_office_address_snippet": "Welwyn Garden City",
      "sic_codes": ["47110"]
    }
  ],
  "meta": {
    "request_id": "req_search_1",
    "generated_at": "2026-03-17T10:00:00Z",
    "cache": "hit"
  },
  "error": null
}
```

#### Notes
- backend should prioritise exact company number matches
- this endpoint should be heavily cached

## 2. Get company aggregate
### GET /api/v1/companies/{company_number}
Returns the main denormalised payload for the company page.

#### Path params
- `company_number` string, required

#### Query params
- `refresh` boolean, optional, default false
- `include` optional comma-separated modules such as `overview,financials,signals`

#### Example response
```json
{
  "data": {
    "company": {
      "company_number": "00445790",
      "company_name": "TESCO PLC",
      "company_status": "active",
      "company_type": "plc",
      "date_of_creation": "1947-11-27",
      "sic_codes": ["47110"]
    },
    "overview": {
      "accounts_next_due": "2026-05-31",
      "accounts_overdue": false,
      "confirmation_statement_next_due": "2026-07-10",
      "confirmation_statement_overdue": false
    },
    "financial_summary": {
      "latest_period_end": "2025-02-24",
      "confidence": 0.94,
      "metrics": {
        "revenue": 1000000.00,
        "net_assets": 250000.00
      }
    },
    "signals": [
      {
        "signal_code": "RECENT_CHARGE_ACTIVITY",
        "severity": "medium",
        "explanation": "New charge activity was recorded in the last 90 days"
      }
    ],
    "freshness": {
      "snapshot_generated_at": "2026-03-17T09:55:00Z",
      "source_last_checked_at": "2026-03-17T09:54:00Z",
      "freshness_status": "fresh"
    }
  },
  "meta": {
    "request_id": "req_company_1",
    "generated_at": "2026-03-17T10:00:00Z"
  },
  "error": null
}
```

#### Behaviour
- if a fresh snapshot exists, return it immediately
- if stale and `refresh=false`, return stale data and enqueue refresh
- if `refresh=true`, allow manual refresh only for authenticated or rate-limited users

## 3. Get company filings
### GET /api/v1/companies/{company_number}/filings
Returns filing history for the company.

#### Query params
- `cursor` optional
- `limit` default 20, max 100
- `category` optional
- `from_date` optional ISO date
- `to_date` optional ISO date

#### Response fields
- filing transaction ID
- category
- type
- description
- action date
- date filed
- document availability
- parse status if relevant

## 4. Get company officers
### GET /api/v1/companies/{company_number}/officers
Returns current and historic officer appointments.

#### Query params
- `status` optional: active, resigned, all
- `limit` optional

#### Response shape
```json
{
  "data": [
    {
      "name": "Jane Doe",
      "role": "director",
      "appointed_on": "2023-01-01",
      "resigned_on": null,
      "nationality": "British",
      "occupation": "Director"
    }
  ],
  "meta": {
    "request_id": "req_officers_1"
  },
  "error": null
}
```

## 5. Get PSC records
### GET /api/v1/companies/{company_number}/psc
Returns persons with significant control.

#### Query params
- `status` optional: active, ceased, all

## 6. Get charges
### GET /api/v1/companies/{company_number}/charges
Returns charges and charge activity.

#### Query params
- `status` optional
- `limit` optional

## 7. Get insolvency data
### GET /api/v1/companies/{company_number}/insolvency
Returns insolvency case details where available.

## 8. Get financials
### GET /api/v1/companies/{company_number}/financials
Returns period-based metrics, series, and confidence information.

#### Query params
- `metrics` optional comma-separated list
- `periods` optional integer, default 5, max 10
- `format` optional: summary, full

#### Example response
```json
{
  "data": {
    "periods": [
      {
        "period_end": "2025-02-24",
        "accounts_type": "small",
        "currency_code": "GBP",
        "confidence": 0.94,
        "facts": {
          "revenue": 1000000.00,
          "gross_profit": 320000.00,
          "net_assets_liabilities": 250000.00
        }
      }
    ],
    "series": {
      "revenue": [
        {"period_end": "2024-02-24", "value": 900000.00},
        {"period_end": "2025-02-24", "value": 1000000.00}
      ]
    },
    "derived": {
      "revenue_growth_yoy": 0.1111,
      "net_assets_growth_yoy": 0.0870
    },
    "confidence": {
      "overall": 0.94,
      "notes": []
    }
  },
  "meta": {
    "request_id": "req_financials_1"
  },
  "error": null
}
```

#### Rules
- missing metrics should be omitted or set to `null`, not zero
- every derived metric should be reproducible from source facts

## 9. Get risk signals
### GET /api/v1/companies/{company_number}/signals
Returns current and historical signals.

#### Query params
- `status` optional: active, resolved, all
- `severity` optional

#### Example response
```json
{
  "data": [
    {
      "signal_code": "NEGATIVE_NET_ASSETS",
      "signal_name": "Negative net assets",
      "category": "financial_health",
      "severity": "high",
      "status": "active",
      "explanation": "Latest extracted net assets value is below zero",
      "evidence": {
        "period_end": "2025-02-24",
        "source_filing_date": "2025-11-15"
      },
      "methodology_version": "1.0.0"
    }
  ],
  "meta": {
    "request_id": "req_signals_1"
  },
  "error": null
}
```

## 10. Get methodology metadata
### GET /api/v1/methodology
Returns the current methodology and parser versions.

#### Response
- supported metrics
- signal definitions
- parser limitations
- version identifiers

## Authenticated user endpoints

## 11. Get current user
### GET /api/v1/me
Returns the current authenticated user profile.

## 12. List watchlists
### GET /api/v1/watchlists
Returns user watchlists.

## 13. Create watchlist
### POST /api/v1/watchlists
#### Request body
```json
{
  "name": "My target companies",
  "description": "Potential clients and partners"
}
```

## 14. Add company to watchlist
### POST /api/v1/watchlists/{watchlist_id}/items
#### Request body
```json
{
  "company_number": "00445790"
}
```

#### Behaviour
- if the company does not yet exist locally, create a lightweight company shell and enqueue a refresh

## 15. Remove company from watchlist
### DELETE /api/v1/watchlists/{watchlist_id}/items/{company_number}

## 16. List alert channels
### GET /api/v1/alert-channels

## 17. Create alert channel
### POST /api/v1/alert-channels
#### Request body
```json
{
  "channel_type": "email",
  "destination": "user@example.com"
}
```

## 18. Trigger manual refresh
### POST /api/v1/companies/{company_number}/refresh
Authenticated and rate-limited.

#### Response
```json
{
  "data": {
    "refresh_run_id": "run_123",
    "status": "queued"
  },
  "meta": {
    "request_id": "req_refresh_1"
  },
  "error": null
}
```

## Internal endpoints
These endpoints should not be exposed publicly.

## 19. Ingest company
### POST /internal/v1/companies/{company_number}/ingest

#### Purpose
- fetch and upsert latest company profile and related entities

#### Request body
```json
{
  "force": false,
  "modules": ["profile", "filings", "officers", "psc", "charges", "insolvency"]
}
```

## 20. Fetch filing document
### POST /internal/v1/filings/{filing_id}/fetch-document

## 21. Parse filing document
### POST /internal/v1/documents/{document_id}/parse

## 22. Recompute risk signals
### POST /internal/v1/companies/{company_number}/signals/recompute

## 23. Rebuild snapshot
### POST /internal/v1/companies/{company_number}/snapshot/rebuild

## 24. Health endpoints
### GET /internal/v1/health
### GET /internal/v1/ready
### GET /internal/v1/metrics

## API contract details

## Search result contract
```json
{
  "company_number": "string",
  "company_name": "string",
  "company_status": "string",
  "company_type": "string|null",
  "date_of_creation": "YYYY-MM-DD|null",
  "registered_office_address_snippet": "string|null",
  "sic_codes": ["string"],
  "match_type": "exact_number|name|fuzzy"
}
```

## Company aggregate contract
Top-level modules should be stable even when subfields evolve.

```json
{
  "company": {},
  "overview": {},
  "filing_summary": {},
  "financial_summary": {},
  "signals": [],
  "officers": [],
  "psc": [],
  "charges": [],
  "insolvency": [],
  "freshness": {},
  "confidence": {}
}
```

## Pagination model
Use cursor-based pagination for lists derived from filing history and large sets.

Response example:
```json
{
  "data": [],
  "meta": {
    "pagination": {
      "next_cursor": "opaque_cursor",
      "limit": 20
    }
  },
  "error": null
}
```

## Response headers
Recommended headers:
- `X-Request-ID`
- `Cache-Control`
- `ETag` for aggregate responses where practical
- `Retry-After` when user-side rate limiting applies

## Status codes
- `200 OK` for successful GET and idempotent operations
- `201 Created` for create operations
- `202 Accepted` for queued background operations
- `400 Bad Request` for invalid input
- `401 Unauthorized`
- `403 Forbidden`
- `404 Not Found`
- `409 Conflict`
- `422 Unprocessable Entity`
- `429 Too Many Requests`
- `500 Internal Server Error`
- `503 Service Unavailable` when critical dependencies fail

## Validation rules
- company number must match known Companies House formatting rules used by your app
- query strings must have minimum and maximum length boundaries
- user-owned resource access must be enforced server-side
- internal endpoints must reject unauthorised callers

## Idempotency
Apply idempotency to:
- company ingest operations
- document fetch operations
- document parse operations
- snapshot rebuild operations

Recommended approach:
- hash request scope and use job-level de-duplication in Redis

## Versioning policy
- additive response changes allowed in minor versions
- breaking changes require `/api/v2`
- methodology versions are separate from API versions

## OpenAPI generation
Generate the OpenAPI spec from FastAPI and commit a frozen schema artifact for the frontend.

Recommended generated files:
- `openapi.json`
- `packages/schemas/src/generated.ts`

## Security requirements
- never proxy arbitrary URLs
- never expose raw third-party credentials
- rate-limit search and refresh endpoints
- validate all query parameters and JSON payloads
- log all internal write operations with request IDs

## Final recommendation
Keep the public API small and stable. Let the frontend rely mainly on:
- search
- company aggregate
- financials
- filings
- signals
- watchlists

Everything else should support those flows or remain internal. That will keep your API maintainable while giving users a rich experience.
