# Invoice Engine release readiness

**Review date:** 2026-11-06  
**Verdict:** NOT READY for a public release

## Audit summary

The active application is the FastAPI service in `api.py` with the `frontend/` directory mounted at `/frontend`. Invoice records and OCR jobs use SQLite. The authenticated API scopes invoice and job access by Supabase user ID. The active dashboard already had retail state sync to `user_workspaces`; earlier descriptions of it as entirely browser-only were inaccurate. Its local cache was global across accounts, its sync status was not visible in the dashboard, and some UI copy described sync inaccurately. Retail state and bill settings are currently scoped to Supabase user IDs, not to a business membership model, so multiple staff cannot share a single business workspace.

## Changes in this preparation pass

- Retail browser cache keys now include the signed-in Supabase user ID. The old unscoped cache is not silently assigned to the first account that signs in. A user can review its record counts and explicitly choose to import it into the current account.
- Retail sync status is visible in the dashboard. Network failures fall back to that account's local cache, and concurrent workspace creation is handled without overwriting saved business settings.
- Bill settings use per-user local cache keys and clearer load/save status. Cloud updates preserve the workspace's retail data. Previous signed-out browser settings remain readable.
- Older unscoped retail and bill settings are not assigned to whichever account signs in first; both have explicit review/import actions.
- Uploads are capped at 25 MB per file and 20 files per request, checked against PDF/image signatures, and written under server-generated names that retain a sanitized display label.
- The public health endpoint now checks SQLite connectivity and returns HTTP 503 when the database is unavailable.
- Billing and Sales open without a plan chooser. The homepage states that the initial offer is free without a payment method or subscription.
- The Supabase migration explicitly grants workspace operations to authenticated users and denies anonymous access.
- Docker now uses Python 3.12 to match the documented runtime, has a default port and health check, and `.dockerignore` excludes environment files, databases, uploads, outputs, and generated workbooks from the image build context.

## Files changed

- `api.py`
- `frontend/business-tools.html`
- `frontend/dashboard.html`
- `frontend/index.html`
- `supabase_workspace_migration.sql`
- `tests/test_tenant_security.py`
- `Dockerfile`
- `.dockerignore`

## Database migration

No production database was contacted or changed. Review `supabase_workspace_migration.sql`, then run it in the SQL Editor for the Supabase project configured in `frontend/supabase-config.js`. It creates/updates the `user_workspaces` table, enables RLS, and sets owner-only policies and table grants. It does not delete workspace rows. Confirm the resulting policies and test two separate accounts before using customer data.

## Tests performed

- `python -m unittest discover -s tests -v`: 9 tests passed (tenant filters, job isolation, auth route dependencies, missing token rejection, upload validation, and database health-check behavior).
- Python bytecode compilation for `api.py`, `auth.py`, `database.py`, `job_queue.py`, and `worker.py`: passed.
- Node syntax checks for inline scripts in `dashboard.html`, `business-tools.html`, and `auth.html`: passed.
- `git diff --check`: passed.
- Docker build, browser workflows, Supabase migration/persistence, registration, login, Google OAuth, OCR, PDF printing, export downloads, and mobile behavior were not run.

## Remaining release blockers

- Apply the Supabase migration and run account A/account B tests for settings, retail state, and RLS. The current data model is per-user, not a shared business with staff membership.
- Test registration, email verification, login/logout, password reset, and Google OAuth against the deployed Supabase configuration.
- Complete real workflows for upload/extraction, duplicate handling, billing/GST, printed invoices, stock deductions, sales reports, and exports. The tests currently cover API tenant behavior only.
- Decide whether local-only historic retail data should be migrated, and verify the explicit import flow with representative records.
- Bill numbering is generated in the browser and is not a server-enforced sequential counter. The retail ledger and printable receipts are not integrated with backend invoice records or OCR purchases. Do not treat them as a legally complete invoicing/accounting system without further implementation and validation.
- Add accurate Privacy Policy, Terms of Service, and support contact details. The privacy notice must explain authentication, uploaded financial documents, Supabase storage, and AI extraction processing. Contact and legal terms must be supplied by the business owner rather than invented.
- Add production rate/abuse controls, operational spending alerts, backup/restore procedures, and retention rules. Do not depend on ephemeral container storage for SQLite, uploads, or outputs.
- Confirm Voroa's persistent-volume, port, process, and worker expectations. The Docker image still starts the worker in the API container; worker/API failure monitoring and split-service deployment have not been verified.

## Deployment and operational notes

**Voroa data durability is a release blocker:** its current service disk documentation says files written to a web service or worker are temporary and can be erased on deploy or at other times. This app stores SQLite, uploads, and outputs on local paths by default. Move those records/files to managed persistent database/object storage before production; a local container path is not sufficient on this host. See [Voroa service disk](https://getvoroa.com/docs/service-disk/) and [Voroa Docker deployment](https://getvoroa.com/docs/docker/).

Build the Docker image from the repository root after reviewing the diff. Supply secrets through the host's secret/environment configuration, never the frontend: `MISTRAL_API_KEY`, `SUPABASE_URL`, and `SUPABASE_ANON_KEY`. Set `DATABASE_PATH` to the same persistent database location for API and worker if they run separately. The browser Supabase publishable key is public by design; never use a service-role key in frontend code. Keep persistent storage for the SQLite database, uploads, and generated outputs, and back it up before any migration or release.

Expected costs depend on actual Voroa hosting/storage/network usage, Supabase plan and usage, and Mistral OCR/AI volume. No reliable amount can be estimated from this checkout alone. Set provider spending alerts and monitor upload volume, storage, and AI calls before inviting public users.
