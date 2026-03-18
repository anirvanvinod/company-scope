# AI Analysis Layer Spec

## Purpose

This document defines the role, constraints, inputs, outputs, prompt structure,
and behavioural boundaries of the AI narrative layer in CompanyScope.

The AI layer is a **synthesis and communication layer** that operates strictly
on top of structured, pre-computed evidence.  It does not extract facts, parse
filings, invent values, or produce recommendations.

---

## Model selection

Phase 6 uses an open-source or self-hosted language model deployed within the
CompanyScope infrastructure.  No data is sent to third-party hosted AI APIs
unless the user has explicitly consented.

Recommended baseline: `mistral-7b-instruct` or equivalent instruction-tuned
model with a 8 k+ context window.  The model is accessed via a local inference
endpoint (e.g. Ollama, vLLM) and called from the API service.

The model choice may be upgraded without changing the prompt contract defined
in this spec, provided the output schema remains identical.

---

## Strict role definition

| The AI layer IS | The AI layer IS NOT |
|---|---|
| A structured fact summariser | A financial analyst |
| A language formatter for pre-computed signals | A parser or extractor |
| A caveat-aware narrator | An investment advisor |
| A confidence communicator | A regulator or credit scorer |
| A synthesis engine over structured inputs | An inventor of facts |

The model **never** speaks with certainty that goes beyond the evidence passed
to it.  Every narrative sentence must be traceable to a specific input field.

---

## Allowed inputs

The AI function receives a single structured context object.  No raw documents
or unstructured text are passed.

### Input schema (`AnalysisContext`)

```json
{
  "company": {
    "company_number": "string",
    "company_name": "string",
    "company_status": "string",
    "company_type": "string",
    "sic_codes": ["string"],
    "date_of_creation": "YYYY-MM-DD or null",
    "accounts_overdue": "boolean"
  },
  "primary_period": {
    "period_end": "YYYY-MM-DD",
    "period_start": "YYYY-MM-DD or null",
    "accounts_type": "string or null",
    "currency_code": "string",
    "extraction_confidence": "decimal",
    "confidence_band": "high | medium | low | unavailable"
  },
  "facts": {
    "revenue": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "gross_profit": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "operating_profit_loss": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "profit_loss_after_tax": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "current_assets": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "fixed_assets": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "total_assets_less_current_liabilities": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "creditors_due_within_one_year": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "creditors_due_after_one_year": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "net_assets_liabilities": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "cash_bank_on_hand": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "average_number_of_employees": {"value": "decimal or null", "confidence": "decimal", "band": "string"}
  },
  "derived_metrics": {
    "gross_profit_margin": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "operating_profit_margin": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "net_profit_margin": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "current_ratio": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "leverage": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "revenue_growth": {"value": "decimal or null", "confidence": "decimal", "band": "string"},
    "net_assets_growth": {"value": "decimal or null", "confidence": "decimal", "band": "string"}
  },
  "signals": [
    {
      "signal_key": "string",
      "severity": "high | medium | low | informational",
      "fired": "boolean",
      "evidence_summary": "string"
    }
  ],
  "data_quality": {
    "facts_available_count": "integer",
    "facts_total": 12,
    "primary_period_confidence_band": "string",
    "has_prior_period": "boolean",
    "warnings": ["string"]
  }
}
```

### What is never passed to the model

- Raw filing document bytes or text
- Unstructured HTML or XML
- Other companies' data for comparison
- User PII
- Internal system configuration

---

## Forbidden model behaviours

These are enforced through prompt design and post-generation validation.

1. **Do not invent facts.**  The model must not state a figure that does not
   appear in the input context.
2. **Do not make investment, credit, or legal recommendations.**  Phrases such
   as "safe to invest", "creditworthy", "recommend", "do not use", "avoid" are
   prohibited.
3. **Do not predict the future.**  The model must not use forward-looking
   language ("will", "is likely to") except when quoting an official signal
   status such as `accounts_overdue`.
4. **Do not assess management quality.**  Commentary about leadership, strategy,
   or team is out of scope.
5. **Do not produce a risk score.**  The model produces narrative, not a
   composite numeric score.
6. **Do not speak with false confidence.**  Where the input shows `null` values
   or `low`/`unavailable` confidence, the narrative must reflect this.
7. **Do not repeat data outside what was provided.**  The model must not cite
   sector averages, market context, or benchmarks unless they appear in the
   input (they do not in Phase 6).

---

## Prompt structure

The prompt is a fixed system prompt followed by a serialised JSON context.
The model is called once per company view.  The result is cached against
`(company_id, primary_period_id, methodology_version, model_version)`.

### System prompt

```
You are a structured financial data interpreter for a UK company intelligence
platform.

Your job is to produce a concise, forensic, evidence-bound narrative summary of
a UK company based exclusively on the structured data provided to you. You are
not a financial advisor, investment analyst, or credit officer.

Rules you must always follow:
- Every statement you make must be directly traceable to a field in the input.
- Do not invent figures, trends, or context that are not in the input.
- Where data is marked null or unavailable, say so plainly. Do not fill gaps
  with assumptions.
- Do not recommend any course of action.
- Do not score the company.
- Do not predict future performance.
- Use plain, direct British English. Avoid marketing language.
- Where confidence is low or unavailable, state this limitation explicitly.
- Use past tense when referring to filed figures ("the company reported",
  "accounts showed").
- Flag data quality limitations at the end of the summary if they are material.

Output format: structured JSON matching the output schema provided.
```

### User message

The context object serialised as JSON, preceded by:

```
Analyse the following company data and produce a structured narrative summary.
```

---

## Output schema

The model must return valid JSON.  The API validates this before caching or
returning to the client.  If the model returns invalid JSON or a schema
violation, the API falls back to a template-generated summary (see below).

```json
{
  "summary_short": "string, max 280 characters",
  "narrative_paragraphs": [
    {
      "topic": "financial_overview | liquidity | leverage | growth | data_quality",
      "text": "string, 1-3 sentences",
      "confidence_note": "string or null"
    }
  ],
  "key_observations": [
    {
      "observation": "string, one sentence",
      "severity": "high | medium | low | informational",
      "evidence_ref": "metric or fact key this is based on"
    }
  ],
  "data_quality_note": "string or null",
  "caveats": [
    "string"
  ]
}
```

### Field constraints

- `summary_short`: plain factual statement, no adjectives like "strong",
  "weak", "excellent", "poor" unless directly referencing a signal severity.
- `narrative_paragraphs`: maximum 5 paragraphs.  Missing topics are omitted,
  not padded.
- `key_observations`: maximum 5 observations.  These must correspond 1:1 to
  fired signals or explicitly named metric anomalies.
- `data_quality_note`: populated when `data_quality.facts_available_count < 6`
  or any `warnings` are present.
- `caveats`: always includes the standard platform caveat; may include
  data-specific caveats.

### Standard caveat (always appended)

```
This summary is based on public filing data extracted from Companies House
records. It is informational only and does not constitute investment, credit,
legal, or accounting advice. Data may be incomplete, delayed, or subject to
restatement.
```

---

## Tone and voice

The AI layer should sound like a **careful, experienced financial analyst
reading from a structured brief**.  Not a chatbot.  Not a dashboard widget
copy-writer.

| Desired | Avoid |
|---|---|
| Forensic and precise | Vague and impressionistic |
| Evidence-citing | Opinion-stating |
| Plainly confident where evidence is strong | Falsely reassuring |
| Plainly limited where evidence is absent | Filling silence with filler |
| British English, past tense for filed figures | Americanisms, present-tense claims about the future |
| Short declarative sentences | Long hedged compound sentences |

### Example tone contrast

**Wrong:** "This company appears to be in a strong financial position with
healthy liquidity, making it a potentially attractive investment opportunity."

**Correct:** "For the period ending 31 December 2023, the company reported
revenue of £4.2m and a net profit margin of 12.4% (medium confidence). Current
assets covered creditors due within one year at a ratio of 1.8, indicating
adequate short-term coverage at the time of filing."

---

## Fallback template

If the model returns invalid JSON, times out, or fails, the API generates a
deterministic template-based summary from the same `AnalysisContext` object.
This fallback:

- shows available metric values verbatim
- lists fired signals with their severity and evidence summary
- appends the standard caveat
- is clearly marked as `source: "template"` not `source: "ai"`

The fallback ensures the page always renders meaningful content without AI.

---

## Caching

AI output is cached in Redis with a TTL of 24 hours, keyed on:
`ai_summary:{company_id}:{primary_period_id}:{methodology_version}:{model_version}`

Cache is invalidated when:
- a new `financial_period` is ingested for the company
- `METHODOLOGY_VERSION` increments
- the model version changes

---

## Latency budget

The AI call must complete within 8 seconds.  The API returns the cached or
template summary immediately and queues the AI call asynchronously if no cached
result exists.  The client polls or uses a WebSocket subscription to receive
the AI summary when ready.

---

## What this spec does not cover

- Model training or fine-tuning (not required; instruction-following is
  sufficient for structured summarisation)
- Multi-language support (English only in Phase 6)
- Company comparison narratives (post-MVP)
- AI-generated signals (all signals are rule-based per
  `docs/09-financial-analysis-spec.md`)
