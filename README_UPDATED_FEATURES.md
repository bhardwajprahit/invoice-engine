# Invoice Engine — Updated feature bundle

This is a **separate working copy**. It does not overwrite your current project. It uses the authenticated API/database/worker versions supplied in your files and preserves the dashboard version with the restored Excel-export fixes.

## Included
- Existing invoice OCR / extraction / validation / Excel workflows and dashboard.
- Authenticated, per-user invoice and job routes from the supplied secure API version.
- GSTIN **format** checker and direct link to the official GST taxpayer search portal. The app does not claim that a format check verifies registration status. Automated live verification requires an authorized API/provider and credentials.
- Customizable printable bill builder: shop details, GSTIN, customer, line items, HSN/SAC, quantity, price, tax rates, discount, tax split, invoice number/date, print/PDF. It is a template, not GSTN filing or IRN generation.
- Cloud sync for the existing browser-stored retail workspace (products, sales, purchases, customers) and cloud-backed business settings, using a Supabase row protected by RLS. Local browser storage remains as a fallback.
- Supabase SQL migration, tenant security tests, requirements and setup guide.

## Critical setup before cloud sync works
1. Keep your original project unchanged; extract this ZIP into a new folder.
2. Verify `frontend/supabase-config.js` points to the intended Supabase project. It contains only the browser publishable/anon key; never place a service-role key in it.
3. Open the Supabase SQL Editor and run `supabase_workspace_migration.sql`. This creates the RLS-protected `user_workspaces` table.
4. Configure API environment variables (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) and the same persistent `DATABASE_PATH` for API and worker. Follow `SECURITY_MIGRATION.md` for safely assigning legacy invoices to their owner.
5. Configure the worker as a separate long-running process. Local `uploads/` and `outputs/` folders must be on persistent/shared storage for production.
6. Start with dummy data and test with two separate accounts before any customer data.

## Important current limitations
- The new Supabase sync currently covers **Billing/Sales retail state and bill settings**, not the existing SQLite invoice records, uploaded documents, OCR jobs or generated Excel files. Those remain on the backend's configured database/filesystem. Full cross-device invoice/upload sync needs a shared persistent backend/storage migration.
- Payment gateway checkout, verified webhooks, server-enforced paid plans/quotas, scheduled unpaid-invoice reminders, and authorized live GSTIN API lookup are **not enabled** in this bundle because no merchant/provider credentials or finalized rules were supplied. Do not advertise those as live.
- GST math is a helper for a draft template. Tax applicability, place of supply, HSN/SAC and statutory invoice fields must be confirmed for each business scenario.

## Install / run
Use Python 3.11 or 3.12 in a fresh virtual environment, install `requirements.txt`, install/configure Tesseract OCR for your OS, and set `MISTRAL_API_KEY` in your server environment. Run `uvicorn api:app --host 0.0.0.0 --port 8000`. Run `python worker.py` in a second process. Do not commit `.env`, databases, uploaded documents or generated customer files.

## Tests
Run `python -m unittest discover -s tests -v`. OCR tests that depend on a local sample invoice/Tesseract/Mistral should be run separately with test fixtures.
