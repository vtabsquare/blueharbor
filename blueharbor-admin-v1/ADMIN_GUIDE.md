# BlueHarbor — buyer + admin local POC

The separate administrative console and buyer application share one SQLite database. Buyer design is retained, with live integration changes. This is a local proof of concept, not a production or certified identity-verification system.

## Start in VS Code

Extract the ZIP into a new folder and open it in VS Code. Install Python 3.10+ and Node.js 22.13+ if needed, restart the terminal, then run:

```sh
python run_local.py
```

First run installs locked web dependencies (internet required). The launcher opens the admin page.

- Admin: http://localhost:3000/admin
- Buyer: http://localhost:3000
- Staff email: `admin@blueharbor.local`
- Staff password: generated and printed in the terminal on the first database startup only. Save it, then change it through the staff profile button.
- Buyer testing: the labelled verified demo-account button is retained. This is a synthetic account, not an externally verified company.

Stop with Ctrl+C. Records persist in `data/blueharbor.sqlite3`. Do not run two builds against the same database. If ports are busy, stop the old app or use `python run_local.py --port 3002 --api-port 8002`.

The owner can set `BLUEHARBOR_ADMIN_EMAIL` and `BLUEHARBOR_ADMIN_PASSWORD` (minimum 12 characters) before first startup. These do not reset existing credentials. `BLUEHARBOR_DEMO=0` disables demo access.

## Included screens

| Screen | Working functions |
|---|---|
| Dashboard | Permission-scoped operating totals and attention items |
| Verification | Assigned cases, private evidence previews, document review, correction requests, approval/rejection/suspension |
| Buyers | Registered company details and verification status |
| Products | Details, pricing, minimum quantities, uploaded photos, publication |
| Inventory | Lot receipts, reasoned adjustments, quality holds/releases, expiry and reservations |
| Warehouses & tanks | Locations, capacity/status, whole-lot transfers, manual temperature/oxygen readings |
| Orders | Internal holds, processing/dispatch/delivery and cancellation |
| Shipments | Carrier/reference/ETA fields and custom buyer-visible milestones |
| Insights & Reports | Deterministic stock alerts, operational review and reports |
| Documents | Versioned uploads, informational PDFs, explicit publication/withdrawal |
| Notifications | In-app notices, optional SMTP delivery queue and retries |
| Reports | Operational summaries and CSV order export |
| Staff & access | Administrator/verifier/operations roles, disabling and session revocation |
| Audit trail | Buyer/staff activity, reasons and before/after records |
| Settings | Country document rules, shipping options/fees, alerts and integrations |

New buyers begin unverified. Only staff endpoints can review evidence or approve accounts. Final approval is human-controlled and checks current required documents. Changed evidence starts a new review revision.

Connected buyers receive refresh events checked approximately every two seconds, with a 15-second refresh fallback. Catalog, fees, verification, orders, published documents and notifications use shared persisted records. Private staff notes and other buyers' data stay out of buyer responses. This updates the buyer application itself; no live Excel integration is included. CSV export is available.

Stock is reserved atomically. Held, unpublished and expired lots cannot be newly allocated; allocated quality holds block dispatch. Cancellation restores reservations once. Whole-lot transfers require no reservations and exclude tank-linked lots. Main stages are Confirmed, Processing, Shipped and Delivered, with finer custom milestones. No payment gateway is included.

## Inventory monitoring

Low-stock, expiry, allocated-hold and large-adjustment alerts are calculated from saved database records. Inventory changes trigger checks, and a periodic worker runs while the admin backend is open. Staff review and resolve every alert. Automated verification is reserved for a later Gemini update.

There is no facial recognition/liveness, authoritative registry lookup, real sensor or carrier API connection. Tank readings and shipment events are manually entered.

## Optional email

In-app notifications work immediately. SMTP is off by default. Set `BLUEHARBOR_SMTP_HOST`, `BLUEHARBOR_SMTP_FROM` and, when needed, `BLUEHARBOR_SMTP_USER` / `BLUEHARBOR_SMTP_PASSWORD`. `BLUEHARBOR_SMTP_SECURITY` accepts `ssl` (default port 465) or `starttls` (port 587); `BLUEHARBOR_SMTP_PORT` overrides the port. Restart and enable email in Admin Settings.

Enabling sends future queued notices to registered recipients: only enable with permission to contact them. Historical notices require explicit retries. Demo `.local` addresses are excluded from normal queuing. An interrupted SENDING item requires owner investigation to avoid duplicate delivery. Actual email delivery and email-address confirmation/OTP are not tested/implemented respectively; the SMTP adapter is tested with a mock provider.

## Documents and privacy

Generated PDFs are informational confirmations, packing lists and invoice summaries, not tax-compliant invoices or payment proof. The lightweight Western font does not support all scripts; multilingual PDFs need a font upgrade. Review documents before publishing. Uploaded originals retain their bytes.

Evidence and images are stored in SQLite. Protect the database/backups and do not share or commit them. There is no antivirus scanning, at-rest encryption, enterprise SSO or production retention policy. Keep this POC on localhost; production deployment needs a separate security/infrastructure review.

## Backup, migration and recovery

```sh
python backend/maintenance.py backup
python backend/maintenance.py reset-staff-password admin@blueharbor.local
```

Backup prints a consistent database copy under `data/backups`. Password recovery prompts privately and revokes staff sessions.

For migration from the buyer build, stop it, retain its complete data directory as a backup, and copy the database into this build's `data` folder before startup. Never copy a live SQLite file without matching journal state; prefer SQLite's backup function. Existing records are retained and admin tables added. Keep the old build unchanged.

Offline restore replaces the active database and retains a safety backup:

```sh
python backend/maintenance.py restore "C:/path/to/backup.sqlite3" --confirm RESTORE
```

Stop all app instances first. Set `BLUEHARBOR_API_PORT` if using a custom port so the restore guard checks it. Retain separate copies of important backups.

## Validation

```sh
python -m unittest discover -s backend -p "test_*.py" -v
```

Checks cover permissions, document revisions, concurrent reservations, cancellation, pricing, quality holds, deterministic inventory alerts, private downloads, live refresh events, SMTP delivery and backup integrity. TypeScript checking, targeted lint and production compilation are also checked.
