# Phase 5 — Gemini assistance

This update adds an **advisory-only Gemini Assistance workspace** to the existing BlueHarbor admin application. Existing operational workflows are unchanged.

## Included

- Document field extraction into a review screen.
- Cross-document comparison for invoices, packing lists, certificates, order and shipment records.
- Weight, date, name and identifier inconsistency highlighting.
- Operational exception summaries.
- Buyer-message and document-cover-letter drafting.
- Natural-language search across role-permitted orders, shipments, document metadata, exceptions and buyer compliance records.
- Role-scoped source retrieval.
- Redaction of structured sensitive fields, emails and phone numbers before Gemini/audit use.
- Sensitive identity-document blocklist. Buyer-upload processing is disabled by default.
- Prompt/response/model/source audit records using the existing `ai_jobs` table.
- Citation links to exact database records or source documents.
- Explicit human-review boundary. Gemini has no endpoint that applies operational state changes.

## Human-controlled actions

Gemini does **not** perform buyer verification, quality release, customs clearance, inventory adjustments or financial approvals. Those remain in the pre-existing staff workflows.

## Configuration

Set these values in the backend environment (do not expose them to the browser):

```text
GEMINI_API_KEY=<Google AI Studio / Gemini API key>
GEMINI_MODEL=gemini-3.8-flash
GEMINI_ALLOW_BUYER_DOCUMENTS=false
```

`GEMINI_ALLOW_BUYER_DOCUMENTS` should remain `false` unless your approved data-processing policy permits sending buyer-submitted business documents to Gemini. Identity documents such as passports, Aadhaar/national IDs and representative-ID files remain blocked even when this flag is enabled.

No database migration is required for Phase 5 because the existing `ai_jobs` table is reused for prompt/response audit records.
