# BlueHarbor — Production Administration Guide

The BlueHarbor buyer portal and administrative console rely on a centralized **Supabase PostgreSQL** database for authenticated access, encrypted documents, and state management. The system is designed for enterprise scaling, robust security, and compliance.

## System Architecture

- **Backend API**: Python 3.12 (HTTP server with Supabase PostgreSQL via `psycopg`).
- **Frontend Portals**: NextJS / Vinext (Buyer: Port 3000, Admin: Port 3001).
- **Database / Auth**: Supabase PostgreSQL and Supabase Auth.
- **Proxy**: Caddy (HTTPS, HTTP->HTTPS redirects).
- **Containerization**: Docker and Docker Compose.

## 1. Initial Setup and Deployment

### 1.1 Prerequisites
Ensure the production host has **Docker** and **Docker Compose** installed.
You will need a production Supabase project with Database and Auth configured.

### 1.2 Environment Variables
Ensure you have the following secure environment variables set in `.env` or in your host environment. **Do not commit `.env` into source control or bake it into images.** Use the `.env.example` as a template.

```
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_PUBLISHABLE_KEY=eyJ...
SUPABASE_SECRET_KEY=eyJ...
SUPABASE_DB_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres
BLUEHARBOR_ENCRYPTION_KEY=<FERNET_KEY>
NODE_ENV=production
```

> [!CAUTION]
> The `BLUEHARBOR_ENCRYPTION_KEY` must never be lost. It encrypts all uploaded documents. If lost, previously uploaded documents cannot be recovered.

### 1.3 Running the Services

1. Build and start the infrastructure using Docker Compose:
```sh
docker-compose up --build -d
```
2. Verify startup:
```sh
docker-compose logs -f backend
```
The Python backend enforces strict startup checks and will crash immediately if required secrets are missing.

## 2. Backup and Recovery

### 2.1 Database Backup
BlueHarbor utilizes standard PostgreSQL backups via `pg_dump`.

To manually trigger a backup from within the backend container or a local environment connected to the Supabase instance:
```sh
python backend/maintenance.py backup
```
*This produces a raw `.sql` file in the `backups` directory, scrubbing ownership headers.*

### 2.2 Database Restore
To restore from a backup:
```sh
python backend/maintenance.py restore <backup-file.sql> --confirm RESTORE
```

> [!TIP]
> For production environments, prefer automated daily backups configured directly in the **Supabase Dashboard** (Database -> Backups).

## 3. Account and Access Management

### 3.1 Enterprise SSO / SAML
The portal supports Enterprise SSO via Supabase Auth.
- **Integration**: Access the Supabase Dashboard -> Auth -> Providers -> SAML 2.0. Add your Identity Provider (IdP) metadata (e.g. Azure AD, Okta). 
- **Testing**: Users can now use the `Enterprise Sign-In (SSO)` button on the login screen. Ensure you've mapped email and name claims correctly.

### 3.2 Staff Accounts
Staff accounts are managed strictly within Supabase Auth and the `staff` PostgreSQL table. Password resets for staff must be done through the Supabase Dashboard or self-service password recovery flow. Local owner reset scripts are deprecated for security.

### 3.3 Account Deletion (GDPR/Compliance)
Buyers can request account deletion or data export.
- **Export**: The system implements `POST /api/export` to bundle and provide all user data.
- **Deletion**: The `POST /api/delete-account` endpoint completely drops all Personally Identifiable Information (PII) while preserving immutable audit logs required for financial compliance.

## 4. Manual Verification & Testing

If executing test suites manually:
- **E2E Testing (Playwright)**: Requires a dedicated local Supabase testing instance (e.g., via `supabase start`). Run `npm run test` within `blueharbor-buyer-portal` and `blueharbor-admin-v1`.
- **Load Testing (Locust)**: Requires a dedicated test environment. Never run load tests against production as it may lock database tables or trigger cloud provider rate limits.
- **Accessibility (WCAG)**: Use Lighthouse or Axe Developer Tools on the running local preview (`npm run dev`) to ensure focus contrast and ARIA labels comply with WCAG 2.2.

## 5. System Monitoring

The backend API issues **Structured JSON Logs** to standard output, ensuring easy ingestion by Datadog, AWS CloudWatch, or ELK stacks.
- All requests include `X-Request-ID` headers for end-to-end tracing.
- Server health and database connection readiness can be checked at `GET /api/health`. Load balancers (e.g. AWS ALB, Caddy) should poll this endpoint.
