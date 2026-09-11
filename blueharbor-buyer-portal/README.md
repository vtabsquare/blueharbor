# BlueHarbor Buyer — independent Supabase application

## Buyer tracking refinement

This buyer-only update replaces the illustrated vessels with representative maritime photographs, reorganizes the shipment workspace, prevents the port rotation from clipping, and gives loading/discharge ports stronger visual priority than intermediate calls. The map now accepts PostgreSQL numeric coordinate values, displays the complete rotation and cargo route, and always shows a vessel marker. Confirmed carrier or staff coordinates take priority; before an actual position arrives, the marker is explicitly labelled as a schedule-estimated position calculated from the published port-call times.

No new Supabase SQL is required for this refinement. The existing Phase 3 and Phase 3.1 tables are unchanged. Environment files are excluded from the update package.

## Phase 3.1 secure access and vessel journeys

The buyer portal now requires sign-in before marketplace or order data is shown. Each allocated order displays its vessel image, carrier, voyage, complete port rotation and the highlighted loading-to-discharge cargo window that serves the buyer's destination. Planned rotation data and confirmed position events remain visually distinct.

The current shared Supabase project has already received `db/08_vessel_rotations_auto_allocation.sql`; do not run it again there. Run scripts 01 through 08 in order for a fresh project. No `.env` file is included in update packages.

## Phase 3 shipping and live tracking

The order tracking workspace now combines shipment route, animated map, vessel/voyage details, container and reefer status, customs milestones, operational exceptions, and the Phase 2 order-document gates. Run `db/07_shipping_customs_tracking.sql` only for a database that has not received Phase 3. It has already been applied to the currently configured Supabase project. Carrier events and staff-entered events are labelled separately.

## Phase 3 shipping, customs and live tracking

This version adds an animated shipment map, route legs and transshipments, container/seal/VGM information, customs milestones, reefer condition updates, ETA history and operational alerts inside each order. Staff-entered events and future carrier-reported events are labelled separately.

The shared Supabase project has already been updated with `db/07_shipping_customs_tracking.sql`. Do not run it again on the current project. For a fresh Supabase project, run scripts 01 through 07 in numeric order.

Map tiles load from OpenFreeMap and therefore need internet access. Positions are confirmed operational events; the application does not invent continuous vessel GPS positions between events.

## Phase 2 database update

Run `db/05_phase2_document_compliance.sql` once in the Supabase SQL Editor before starting this version. The buyer Documentation workspace then shows per-order requirements and released clearance packs. Existing records are preserved. Environment files are not included in update packages.

This ZIP contains only the buyer application and its own Python backend. It does not start or require the other application's folder. The existing interface is preserved using the Sites workflow; there is no combined launcher.

## Keep your current setup

Extract into a NEW folder, for example:

`D:\Python\Project Blueharbor\blueharbor-buyer-supabase`

Do not overwrite your existing buyer or admin folder. Do not copy old SQLite files or old passwords into this version. You may leave the other application closed while using this one.

## Where to enter the Supabase settings

Open this entire project folder in VS Code. Inside its **backend** folder, copy **.env.example** to **.env**, keeping both files in that backend folder.

Your configuration file will therefore be:

`D:\Python\Project Blueharbor\blueharbor-buyer-supabase\backend\.env`

Fill these values there:

```dotenv
SUPABASE_URL=https://atlubtjwhsridpqeutao.supabase.co
SUPABASE_PUBLISHABLE_KEY=your_publishable_or_legacy_anon_key
SUPABASE_SECRET_KEY=your_secret_or_legacy_service_role_key
SUPABASE_DB_URL=your_complete_session_pooler_postgresql_uri
```

The keys and URI above are placeholders, not usable credentials. The URL is already filled in the supplied template. Get keys from Supabase project settings → API Keys. Get the URI from **Connect → Session pooler**, port **5432**; insert your database password and URL-encode special characters in that password. Do not use transaction port 6543.

This existing Python-based integration needs the database URI as well as URL and API keys. Both applications need their **own backend/.env** with settings for the **same Supabase project**. They never read each other's files. These are private server settings; never place them in frontend code, VITE_* or NEXT_PUBLIC_* variables, upload them, or send them in chat.

## Create the common database once

Download the separate **blueharbor-supabase-setup.zip**. Follow its README and run scripts 01 and 02 once for the shared project. Create the first administrator in Supabase Auth and link it using script 03. Optional script 04 adds synthetic inventory; script 05 checks setup.

If scripts 01/02 from the previous package were already run successfully, they are the same scripts: do not delete tables or create another database. Do not run script 03 for an ordinary buyer.

## Start only this application

Requirements: Python 3.12+ and Node.js 22.13+. In this application's VS Code terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe run_local.py
```

If Python is not on PATH, use its installed executable's full path for the first command. The script installs this frontend's packages on first run.

Default website: **http://localhost:3000/**. Its own local API normally uses port **8001**. Busy ports are replaced with free ports; use the printed website address. No unrelated process is stopped. Ctrl+C stops only this application's services.

Register and confirm your email, then sign in. For controlled testing, you can instead create a confirmed buyer in Supabase Authentication → Users. Complete your company profile and upload synthetic verification documents; an admin must approve trading access. There is no default verified account or one-click login.

## Test communication

Start the other app from its OWN project in a separate VS Code terminal. Both write to/read the same Supabase database. Approve a buyer in admin and check buyer verification; place an order in buyer and check admin orders/stock; change shipment details in admin and check buyer tracking.

Each backend listens to committed changes in PostgreSQL and refreshes its own authenticated browser. A 15-second refresh is retained as fallback. There is no cross-app API dependency or shared local database. Background stock/AI monitoring runs only while the **admin** backend is running; buyer browsing/ordering does not require admin to be open.

## Important limits

Only the project URL has been supplied: your live connection, Auth emails, private Storage and real-time timing still need your credentials and testing. No existing SQLite records/passwords are migrated automatically. The buyer assistant requires a server-side Gemini API key; Gemini is not supplied by Supabase. Downloaded CSV/Excel-compatible exports are snapshots, not live-linked spreadsheets.

Auth access tokens expire; sign in again when prompted. There is no new self-service recovery screen. This remains localhost-only POC software; do not expose development ports publicly. See the separate setup guide for security, recovery, SMTP and production limitations.

## Gemini buyer assistant

The buyer-side floating assistant is powered by Gemini from the Python backend. It is deliberately scoped to the signed-in buyer's own BlueHarbor orders, shipment milestones, buyer-visible exceptions, ETA history and released trade-document status. Uploaded verification/identity document contents are not sent to Gemini.

Add the following only to `backend/.env` on the server and restart the app:

```env
GEMINI_API_KEY=your_server_side_key
GEMINI_MODEL=gemini-3.8-flash
```

The API key is removed from the frontend child-process environment by `run_local.py`. The assistant can summarize delays and document status, draft operational messages/claim descriptions and explain records in a requested language. It cannot perform verification, quality, customs, inventory or financial approvals.

## PDF buyer documents

`/api/confirmation/<order-id>` now returns a real PDF instead of HTML. BlueHarbor-generated Order confirmation, Informational invoice and Packing list templates use the same professional ReportLab layout with a branded header, fish mark, buyer/route details, line-item table, cost summary and document disclaimer. `reportlab` is included in `backend/requirements.txt`.
