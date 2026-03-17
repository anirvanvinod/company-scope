# Front-End Wireframes

## Purpose
This document defines the information architecture, page structure, and interaction model for the CompanyScope frontend.

The goal is not pixel-perfect design. The goal is to provide a clear implementation blueprint for Cursor and future designers.

## Product principles
- Fast first impression
- Search-first experience
- Evidence visible everywhere
- Explainability over hype
- Clear confidence and caveat states
- Clean, premium, data-rich interface

## Design system assumptions
- Next.js app router
- Tailwind CSS
- shadcn/ui components
- responsive layout
- accessible colours and keyboard navigation
- light mode first, dark mode optional later

## Global layout

```text
+----------------------------------------------------------------------------------+
| Top nav: Logo | Search bar | Compare | Watchlist | Methodology | Sign in        |
+----------------------------------------------------------------------------------+
| Page content                                                                     |
|                                                                                  |
+----------------------------------------------------------------------------------+
| Footer: Data sources | Methodology | Terms | Privacy | API status               |
+----------------------------------------------------------------------------------+
```

## Primary routes
- `/`
- `/search`
- `/companies/[companyNumber]`
- `/companies/[companyNumber]/financials`
- `/companies/[companyNumber]/filings`
- `/companies/[companyNumber]/officers`
- `/companies/[companyNumber]/ownership`
- `/companies/[companyNumber]/charges`
- `/watchlist`
- `/methodology`
- `/auth/sign-in`

## 1. Home page

### Goal
Get users to search immediately and understand the product in one glance.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Nav                                                                              |
+----------------------------------------------------------------------------------+
| Hero title: "Search any UK company. Understand the signals behind the filings." |
| Subtitle: explainable public-data intelligence from Companies House             |
|                                                                                  |
| [ Large search input ............................................... ][ Search ] |
|                                                                                  |
| Example searches: Monzo Bank Ltd | Deliveroo | BrewDog PLC                     |
+----------------------------------------------------------------------------------+
| 3 value cards                                                                    |
| [Company overview] [Financial trends] [Risk signals]                            |
+----------------------------------------------------------------------------------+
| Methodology teaser                                                               |
| "Every signal links back to source filings and confidence levels."              |
+----------------------------------------------------------------------------------+
```

### Notes
- hero search should support instant typeahead
- keep copy precise and non-promissory
- include subtle disclaimer link near search

## 2. Search results page

### Goal
Help users pick the correct company quickly.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Search input with current query                                                  |
+----------------------------------------------------------------------------------+
| Filters: [Active] [Dissolved] [Company type] [Location later] [SIC later]      |
+----------------------------------------------------------------------------------+
| Result list                                                                      |
|                                                                                  |
| [Company name]                          [Active badge]                           |
| Company no | Type | Incorporated | SIC summary                                  |
| Address snippet                                                                 |
| [Open company]                                                                  |
|----------------------------------------------------------------------------------|
| [Company name]                          [Dissolved badge]                        |
| ...                                                                              |
+----------------------------------------------------------------------------------+
```

### Notes
- exact company number match should rank first
- active status badge should be visually obvious
- result row should be fully clickable
- search state must handle no results cleanly

## 3. Company overview page

### Goal
Provide a complete first-screen summary before the user dives deeper.

### Page layout

```text
+----------------------------------------------------------------------------------+
| Breadcrumb / Search                                                              |
+----------------------------------------------------------------------------------+
| Company header                                                                   |
| Company name                     [Active] [Private limited]                      |
| Company no | Incorporated | SIC | Registered office                             |
| CTA: [Add to watchlist] [Refresh] [Share later]                                 |
+----------------------------------------------------------------------------------+
| Alert row                                                                        |
| [High risk signal] [Medium governance signal] [Confidence warning]               |
+----------------------------------------------------------------------------------+
| Main grid                                                                        |
|                                                                                  |
| Left column (2/3)                            | Right column (1/3)               |
|----------------------------------------------|-----------------------------------|
| Overview summary card                        | Quick health card                |
| Financial trend chart                        | Filing timeliness card           |
| Filing timeline preview                      | Confidence card                  |
|                                              | Source freshness card            |
+----------------------------------------------------------------------------------+
| Tab nav: Overview | Financials | Filings | Officers | Ownership | Charges      |
+----------------------------------------------------------------------------------+
```

### Overview summary card
Shows:
- status
- type
- incorporation date
- accounts next due
- confirmation statement next due
- last accounts made up date
- recent filing highlights

### Quick health card
Summarises:
- latest revenue if available
- latest net assets if available
- key signal count
- charges summary
- officer churn status

### Confidence card
Shows:
- structured financial coverage
- latest parser confidence band
- disclaimer that confidence refers to extraction reliability

## 4. Financials tab

### Goal
Show time-series trends and the latest extracted financial facts.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Financials tab                                                                   |
+----------------------------------------------------------------------------------+
| Metric switcher: [Revenue] [Net assets] [Cash] [Creditors] [Employees]          |
| Period selector: [3Y] [5Y] [All]                                                |
+----------------------------------------------------------------------------------+
| Main chart                                                                       |
|                                                                                  |
|                          line / bar chart                                        |
|                                                                                  |
+----------------------------------------------------------------------------------+
| Latest facts table                                                               |
| Fact name | Latest value | Period end | Confidence | Source                      |
|----------------------------------------------------------------------------------|
| Revenue   | £...         | 2025-12-31 | High       | Filing link                 |
| ...                                                                              |
+----------------------------------------------------------------------------------+
| Derived metrics card row                                                         |
| [Revenue growth] [Profit margin] [Liquidity proxy] [Net assets growth]          |
+----------------------------------------------------------------------------------+
| Caveats panel                                                                    |
+----------------------------------------------------------------------------------+
```

### Notes
- every metric row should have source chip and confidence chip
- support unavailable states without breaking the chart layout
- do not auto-smooth missing periods
- allow hover tooltips with source period detail

## 5. Filings tab

### Goal
Give users source-level auditability.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Filings tab                                                                      |
+----------------------------------------------------------------------------------+
| Filters: [Accounts] [Confirmation] [Appointments] [Charges] [Insolvency]        |
+----------------------------------------------------------------------------------+
| Filing timeline list                                                             |
|----------------------------------------------------------------------------------|
| Filing date | Filing type | Description | Parser status | [Open source]         |
|----------------------------------------------------------------------------------|
| 2026-01-15  | Accounts    | Micro-entity accounts... | Parsed | [Open]          |
| 2025-11-03  | Officer     | Appointment of director  | N/A    | [Open]          |
| ...                                                                              |
+----------------------------------------------------------------------------------+
```

### Notes
- parser status badges: Parsed / Partial / Unsupported / Pending
- user should always be able to trace analysis back to a filing
- filing filters should be instant and client-side after load where possible

## 6. Officers tab

### Goal
Show governance structure and movement.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Officers tab                                                                     |
+----------------------------------------------------------------------------------+
| Summary cards: [Current officers] [Changes last 12m] [Avg tenure]               |
+----------------------------------------------------------------------------------+
| Officer table                                                                    |
| Name | Role | Appointed | Resigned | Status                                      |
|----------------------------------------------------------------------------------|
| Jane Doe | Director | 2022-04-01 | - | Active                                   |
| ...                                                                              |
+----------------------------------------------------------------------------------+
| Governance insights panel                                                        |
| - Officer churn spike in last 12 months                                          |
| - Long-tenured board                                                             |
+----------------------------------------------------------------------------------+
```

## 7. Ownership tab

### Goal
Show PSC data simply and safely.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Ownership tab                                                                    |
+----------------------------------------------------------------------------------+
| PSC cards                                                                        |
|----------------------------------------------------------------------------------|
| PSC name / entity                                                                |
| Nature of control                                                                |
| Notified date                                                                    |
| Source                                                                           |
|----------------------------------------------------------------------------------|
+----------------------------------------------------------------------------------+
| Ownership explanation panel                                                      |
+----------------------------------------------------------------------------------+
```

### Notes
- avoid overly invasive presentation of personal data
- present only what is supported and necessary
- include source and notice language

## 8. Charges tab

### Goal
Provide financing context.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Charges tab                                                                      |
+----------------------------------------------------------------------------------+
| Summary cards: [Outstanding] [Satisfied] [Recent registrations]                 |
+----------------------------------------------------------------------------------+
| Charges table                                                                    |
| Created | Status | Persons entitled summary | Delivered | Satisfied              |
|----------------------------------------------------------------------------------|
| ...                                                                              |
+----------------------------------------------------------------------------------+
| Context note: charges can indicate financing activity, not automatically risk    |
+----------------------------------------------------------------------------------+
```

## 9. Risk signals panel

### Goal
Expose rule-based findings in an explainable way.

### Component structure

```text
+----------------------------------------------------------------------------------+
| Signal card                                                                      |
| [Severity badge] Signal title                                                    |
| Why this matters                                                                 |
| Evidence: linked filing / field                                                  |
| Methodology link                                                                 |
+----------------------------------------------------------------------------------+
```

### Signal section layout
- high severity first
- grouped by category
- include confidence warnings separately from business risk

## 10. Watchlist page

### Goal
Support retention and repeat monitoring.

### Wireframe

```text
+----------------------------------------------------------------------------------+
| Watchlist                                                                        |
+----------------------------------------------------------------------------------+
| [Create list] [Notification settings]                                            |
+----------------------------------------------------------------------------------+
| Watched companies table                                                          |
| Company | Last update | New filings | Signal changes | Actions                   |
|----------------------------------------------------------------------------------|
| ...                                                                              |
+----------------------------------------------------------------------------------+
```

## 11. Methodology page

### Goal
Build trust through transparency.

### Sections
- what the product is
- data sources
- how financial metrics are derived
- how confidence works
- how signals work
- limitations
- version history

### UX notes
- keep it readable
- use examples
- link from signal cards and confidence chips

## 12. Loading, empty, and failure states

### Loading states
- skeleton cards on company overview
- progressive hydration for secondary panels
- optimistic watchlist add

### Empty states
Examples:
- no structured financials available
- no charges registered
- no current PSC data available
- no watchlist items yet

### Failure states
- search service temporarily unavailable
- company refresh failed, showing cached view
- document parse pending
- partial data loaded

Each failure state should:
- avoid technical jargon where possible
- offer retry where sensible
- indicate whether cached data is being shown

## 13. Mobile behaviour
Prioritise:
- search
- company header
- signal summary
- key financial chart
- tabbed detail views

Use stacked cards and horizontal tab scroller.

## 14. Design tokens and visual cues

### Severity badges
- high
- medium
- low
- informational

### Confidence badges
- high confidence
- medium confidence
- low confidence
- unavailable

### Source chips
Every major metric or signal should have:
- source type
- filing date
- link or tooltip

## 15. Accessibility requirements
- keyboard navigable search results
- visible focus states
- chart alternatives via data tables
- colour not used as sole severity indicator
- semantic headings and table labels
- screen-reader readable badges and alerts

## 16. MVP frontend priorities
Implement first:
1. home page
2. search results
3. company overview
4. financials tab
5. filings tab
6. officers tab
7. watchlist page
8. methodology page

## 17. Deferred UX ideas
- comparison view
- relationship graph
- saved report builder
- advanced filters
- sector benchmark visuals
- collaborative notes
