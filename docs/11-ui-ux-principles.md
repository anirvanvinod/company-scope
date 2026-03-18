# UI/UX Principles

## Purpose

This document defines the design language, interaction patterns, and component
standards for the CompanyScope frontend.

It is the authoritative reference for Phase 6 frontend implementation and for
any future design work.

---

## Design philosophy

CompanyScope is a **professional intelligence product**, not an AI dashboard.
The interface should feel like a high-quality financial terminal or a premium
legal database — calm, precise, and grounded in evidence.

### What this product is not allowed to look like

- A generic SaaS dashboard with coloured KPI cards and animated gauges
- A "powered by AI" marketing surface with glowing gradients and hype copy
- A credit score app with a single verdict circle
- A news aggregator with commentary and opinion panels
- A gamified product with badges, streaks, or engagement hooks

### What it should feel like

- A product built for analysts, founders, and professionals who need facts
- Dense with useful information, never cluttered
- Honest about what it does not know
- Confident where evidence is strong; plainly limited where it is not
- Fast, quiet, and serious

---

## Hierarchy principles

### Information hierarchy for every page

1. **Identity and status** — who this company is, whether it is active
2. **Data freshness** — when this was last updated, from which filing
3. **Key facts** — primary numbers, plainly stated
4. **Derived metrics and signals** — labelled as derived, with confidence
5. **Evidence trail** — links to source filings, extraction metadata
6. **Caveats and limitations** — at the bottom, not hidden, not buried

### Page hierarchy

- Company overview page is the centre of gravity; all other pages branch from it
- Financials tab is a first-class destination with a full URL (`/companies/:id/financials`)
- Filing timeline is evidence, not a feed
- Officers and ownership are facts, not story

---

## Typography

### Fonts

- Primary: a humanist sans-serif with strong small-size legibility
  - Recommended: Inter, IBM Plex Sans, or Geist Sans
  - No display fonts, decorative fonts, or variable-weight animations
- Monospace: for company numbers, filing IDs, raw values, and code
  - Recommended: IBM Plex Mono, JetBrains Mono, or Geist Mono

### Scale

Use a strict typographic scale.  No arbitrary font sizes.

| Role | Size | Weight | Usage |
|---|---|---|---|
| Page title | 24px / 1.5rem | 600 | Company name at page top |
| Section heading | 18px / 1.125rem | 600 | Tab section headers |
| Subsection heading | 14px / 0.875rem | 600 | Card headers, table headers |
| Body | 14px / 0.875rem | 400 | Paragraph text, descriptions |
| Data value | 20px / 1.25rem | 600 | Primary metric values |
| Data label | 12px / 0.75rem | 500 | Metric names, axis labels |
| Caption | 12px / 0.75rem | 400 | Source links, timestamps, caveats |
| Monospace | 13px / 0.8125rem | 400 | Company numbers, IDs, raw values |

### Rules

- No text below 12px
- No ALL-CAPS body text (reserved for status badges only)
- Line height: 1.5 for body, 1.2 for headings, 1.4 for captions
- Maximum line length: 72 characters for body text, unconstrained for data tables

---

## Colour

### Palette

Use a minimal, low-saturation palette.  Reserve strong colour for signal states only.

| Token | Usage | Example hex |
|---|---|---|
| `surface-base` | Page background | `#F9FAFB` |
| `surface-raised` | Cards, panels | `#FFFFFF` |
| `surface-subtle` | Table rows, hover states | `#F3F4F6` |
| `border` | Card borders, dividers | `#E5E7EB` |
| `text-primary` | Headings, metric values | `#111827` |
| `text-secondary` | Labels, descriptions | `#374151` |
| `text-muted` | Captions, metadata | `#6B7280` |
| `text-disabled` | Null/unavailable states | `#9CA3AF` |
| `signal-high` | High severity signals | `#DC2626` (red-600) |
| `signal-medium` | Medium severity signals | `#D97706` (amber-600) |
| `signal-low` | Low severity signals | `#2563EB` (blue-600) |
| `signal-info` | Informational signals | `#059669` (emerald-600) |
| `confidence-high` | High confidence indicator | `#059669` |
| `confidence-medium` | Medium confidence indicator | `#D97706` |
| `confidence-low` | Low confidence indicator | `#9CA3AF` |
| `confidence-unavailable` | Unavailable | `#E5E7EB` |

### Rules

- Colour is never the sole indicator of meaning; always pair with a label
- No gradients, no glass effects, no coloured backgrounds on metric cards
- Dark mode uses the same semantic tokens mapped to inverted values
- Charts use a single hue per series; no rainbow palettes

---

## Whitespace

### Spacing scale

Use an 8px base grid.  Accepted multiples: 4, 8, 12, 16, 24, 32, 48, 64.

| Context | Spacing |
|---|---|
| Inside card | 16–24px padding |
| Between cards | 16px gap |
| Section separation | 32–48px |
| Page horizontal margin | 24px (mobile), 48px (tablet), auto with max-width 1280px (desktop) |
| Between label and value | 4px |
| Between rows in a data table | 12px |

### Rules

- Never use whitespace to hide the absence of content; use an explicit empty state
- Dense but not cramped: prefer showing more useful data over extra whitespace
- Charts have minimum 8px internal padding on all axes

---

## Evidence visibility

Evidence traceability is a product feature, not a footer disclaimer.

### Every metric or signal must show inline

- A source tag: "From accounts filed [date]" or "Companies House profile"
- A confidence indicator (see below)
- A link to the source filing when a filing exists

### Evidence component

A small inline evidence trail anchored to each card:

```
Extracted from: [Companies House] [Annual accounts] [31 Dec 2023] [View filing ↗]
Confidence: ●●●○  Medium
Parser version: 1.0.0
```

This is always visible on hover on desktop; always visible on mobile.

### Null state evidence

When a fact is unavailable, show why, not just a dash:

```
Revenue — Not available
Reason: Document filed as micro-entity accounts (limited disclosure)
Source: Filing 12 Apr 2023
```

Never show a bare `—` or `n/a` without context.

---

## Confidence display

Confidence communicates data quality, not company quality.  The UI must make
this distinction explicit at first encounter (e.g. a tooltip on first render).

### Confidence indicator component

A four-dot pill: filled dots = confidence level.

| Band | Dots | Colour |
|---|---|---|
| High | ●●●● | `confidence-high` |
| Medium | ●●●○ | `confidence-medium` |
| Low | ●●○○ | `confidence-low` |
| Unavailable | ●○○○ | `confidence-unavailable` |

- Always accompanied by the band label (not just the dots)
- Tooltip explains what confidence means: "Reflects data extraction quality, not financial health"
- Never use language like "accuracy" or "reliability score" for the metric value itself

### Derived metric labelling

All derived metrics carry a subtle label: "Derived from [fact names]".

Example: "Current ratio — Derived from current assets ÷ creditors due within one year"

---

## Signal display

Signals are facts about the data, displayed as contextual flags.  They are
not scores, grades, or verdicts.

### Signal card component

```
[●] Negative net assets                          [HIGH]
    Net assets: −£284,000 (period ending Dec 2023)
    Source: Annual accounts filed 14 Mar 2024
    Confidence: ●●●○ Medium
    [What does this mean?]
```

### Rules

- Signal colour (red/amber/blue/green) only appears on the severity indicator, not the card background
- The severity label is a badge, not a banner
- `What does this mean?` links to the methodology page section for this signal
- Informational signals (green) are displayed in a separate section below risk signals
- Maximum 3 high-severity signals displayed in the overview panel; full list on the financials tab

---

## Stale, partial, and missing states

These states are first-class UI states.  They must be designed explicitly, not
treated as edge cases.

### Stale data

Displayed when the most recent financial period is > 12 months old:

```
⚠ Financial data may be dated
Last accounts period: 31 December 2022 (filed 18 months ago)
[Request refresh]
```

The stale notice is at the top of the financials section, below the tab header.

### Partial coverage

When fewer than 6 of 12 canonical facts were extracted:

```
ℹ Limited financial data extracted
Only 4 of 12 standard fields were available in this filing.
This company filed as a micro-entity — reduced disclosure is expected.
[Learn more about disclosure regimes]
```

### Missing period

When no financial period exists at all:

```
No financial facts extracted
Accounts may not have been filed, or the document format was not supported.
[View filing history]
```

### Unavailable confidence

When a metric's confidence is `unavailable`:

```
Current ratio — Unavailable
Insufficient confidence in source data to calculate this metric reliably.
```

Never show a calculated value when confidence is unavailable.

---

## Source traceability

Every piece of financial data links back to its origin.

### Source link component

Appears at the bottom of every metric card and AI summary:

```
Source: Companies House · Annual Report and Accounts
Filed: 18 March 2024 · Period ending: 31 December 2023
Document: [MzAwNTI0NDY5OW...] [View on Companies House ↗]
```

### AI summary source label

AI-generated summaries are clearly attributed:

```
AI summary generated from structured filing data
Model: mistral-7b-instruct · Generated: 18 Mar 2024 · Cache TTL: 24h
[How is this generated?]
```

If the summary came from the template fallback (not AI):

```
Structured summary (AI unavailable)
[How is this generated?]
```

---

## Financial-product interaction patterns

### No hover-only critical information

All signals, confidence indicators, and evidence links must be accessible
without hover.  Hover may enhance (e.g. expand tooltip) but must not be the
only way to access data.

### No auto-refresh without indicator

If data refreshes in the background, show a quiet indicator:
```
● Refreshing  or  ✓ Updated 2m ago
```

### Loading states

- Skeleton screens for data panels, not spinners
- Skeleton shape matches the actual content layout so the page does not reflow on load
- AI summary panel: show a "Generating summary…" skeleton for up to 8 seconds;
  fall back to template summary with a note

### Empty company page

If a company was found but has no financial data at all:

```
[Company name]
[Company number] · [Status] · [Incorporated date]

Financial data not available
No accounts have been successfully extracted for this company.
This may be because the company has not filed accounts, or the document
format was not supported by our extraction pipeline.

[View filing history] [Add to watchlist]
```

---

## Chart design

Charts are reserved for trend data only (3+ periods).  Do not use charts for
single-period data; use a plain value display instead.

### Principles

- Line charts for trend data; bar charts for period-on-period comparisons
- No pie charts (no part-of-whole financial facts in MVP)
- X-axis: period end dates, formatted as "Dec 23", "Dec 22", etc.
- Y-axis: GBP values formatted with £ prefix and k/m suffix at scale
- Confidence shown as a shaded band around the line (opacity 15%)
- Null periods shown as a gap in the line, not interpolated
- Comparison line (prior year) shown as dashed, same hue, lower opacity

### Chart labels

- No chart title bar (the section heading serves this role)
- X-axis label: year/period
- Y-axis label: "£ (thousands)" or "Ratio" as appropriate
- Tooltip: exact value, period, confidence band, source filing link

---

## Responsive behaviour

| Breakpoint | Layout |
|---|---|
| < 640px (mobile) | Single column; metrics stack vertically; charts full-width; signals full-width |
| 640–1024px (tablet) | Two-column metric grid; company header stacks |
| > 1024px (desktop) | Three-column metric grid; company header inline; sidebar signals panel |

All data tables scroll horizontally on narrow viewports; columns are never
truncated unless explicitly labelled.

---

## Accessibility

- WCAG 2.1 AA minimum
- All colour usage has at least 4.5:1 contrast ratio against its background
- Signal severity is communicated with icon + text, not colour alone
- All interactive elements have visible focus rings
- Charts have accessible table equivalents behind a toggle
- All linked filing documents open in a new tab with `rel="noopener noreferrer"`

---

## Anti-patterns

These are explicitly banned regardless of implementation convenience.

| Anti-pattern | Why banned |
|---|---|
| Composite "health score" dial or gauge | Implies certainty and invites misuse; no single score captures evidence complexity |
| Animated number counters | Theatre, not information |
| Coloured background cards for signals | Invites reading severity as a verdict on the company |
| "AI-powered" badge or hero claim | Positions the AI as the product rather than the evidence |
| Auto-playing tooltips or walkthrough overlays | Condescending; assume professional users |
| Confidence displayed as a percentage number | "67% confident" is misleading; band labels are more honest |
| Empty state with only an illustration | Useless for professionals; replace with specific reason and action |
| Progress bars for "data completeness" | Implies completeness is always achievable; prefer specific counts |
