# BlueHarbor Admin — independent Supabase application

## Phase 3.1 vessel journeys and automatic allocation

The control tower now shows each vessel's complete port rotation and highlights the loading-to-discharge cargo window for each order. Active orders are automatically matched to a future sailing by destination, departure, available TEU and reefer capacity. Available vessels include imagery, voyage, full call sequence and remaining capacity. Manual plans remain under Operational overrides. Schedule samples and future carrier-reported data are labelled separately.

The current shared Supabase project has already received `db/08_vessel_rotations_auto_allocation.sql`; do not run it again there. Run scripts 01 through 08 in order for a fresh project. No `.env` file is included in update packages.

## Phase 3 shipping control tower

This version adds carrier booking and route planning, transshipment legs, container/seal/VGM controls, Shipping Bill/e-SANCHIT/LEO/EGM milestones, reefer readings, ETA history, operational exceptions and an animated map. Staff-entered events and future carrier-reported events are labelled separately.

The shared Supabase project has already been updated with `db/07_shipping_customs_tracking.sql`. Do not run it again on the current project. For a fresh Supabase project, run scripts 01 through 07 in numeric order.

Use Shipping from the main navigation. Automatic allocation supplies the vessel journey first; staff then record container/VGM details, customs gates and confirmed movement. Map tiles load from OpenFreeMap and need internet access. Carrier API ingestion remains a later integration; current operational events are staff-entered and clearly marked.

## Phase 2 database update

Run `db/05_phase2_document_compliance.sql` once in the Supabase SQL Editor before starting this version. The Trade documents workspace then includes order readiness, controlled releases, exporter credentials, and destination rule packs. Existing records are preserved. Environment files are not included in update packages.

This ZIP contains only the admin application and its own Python backend. It does not start or require the other application's folder. The existing interface is preserved using the Sites workflow; there is no combined launcher.

## Keep your current setup

Extract into a NEW folder, for example:

`D:\Python\Project Blueharbor\blueharbor-admin-supabase`

Do not overwrite your existing buyer or admin folder. Do not copy old SQLite files or old passwords into this version. You may leave the other application closed while using this one.

## Supabase settings

Updates intentionally exclude every `.env` file. Keep the working `backend/.env` already configured on your computer; replacing application files does not require changing it.

Your configuration file will therefore be:

`D:\Python\Project Blueharbor\blueharbor-admin-supabase\backend\.env`

For a first-time installation, create `backend/.env` locally with these names:

```dotenv
SUPABASE_URL=https://atlubtjwhsridpqeutao.supabase.co
SUPABASE_PUBLISHABLE_KEY=your_publishable_or_legacy_anon_key
SUPABASE_SECRET_KEY=your_secret_or_legacy_service_role_key
SUPABASE_DB_URL=your_complete_session_pooler_postgresql_uri
```

The values above are placeholders, not usable credentials. Get keys from Supabase project settings → API Keys. Get the URI from **Connect → Session pooler**, port **5432**; insert your database password and URL-encode special characters in that password. Do not use transaction port 6543.

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

Default website: **http://localhost:3001/admin**. Its own local API normally uses port **8002**. Busy ports are replaced with free ports; use the printed website address. No unrelated process is stopped. Ctrl+C stops only this application's services.

Sign in with the email/password you created in Supabase and linked using script 03. There is no default password. Additional staff are managed here; buyer registration does not grant staff access. The optional BLUEHARBOR_BUYER_URL in backend/.env controls only the navigation link to buyer; update it if the buyer launcher chose another port.

## Test communication

Start the other app from its OWN project in a separate VS Code terminal. Both write to/read the same Supabase database. Approve a buyer in admin and check buyer verification; place an order in buyer and check admin orders/stock; change shipment details in admin and check buyer tracking.

Each backend listens to committed changes in PostgreSQL and refreshes its own authenticated browser. A 15-second refresh is retained as fallback. There is no cross-app API dependency or shared local database. Background stock monitoring runs only while the **admin** backend is running; buyer browsing/ordering does not require admin to be open.

## Important limits

Only the project URL has been supplied: your live connection, Auth emails, private Storage and real-time timing still need your credentials and testing. No existing SQLite records/passwords are migrated automatically. Automated verification is reserved for a later Gemini update; this release uses staff decisions and deterministic inventory rules. Downloaded CSV/Excel-compatible exports are snapshots, not live-linked spreadsheets.

Auth access tokens expire; sign in again when prompted. There is no new self-service recovery screen. This remains localhost-only POC software; do not expose development ports publicly. See the separate setup guide for security, recovery, SMTP and production limitations.
