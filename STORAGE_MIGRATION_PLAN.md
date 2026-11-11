# Invoice Engine — Storage Migration Plan (Staging First)

**Prepared:** 6 November 2026  
**Status:** Audit and design only. No application code, live database, storage bucket, deployment, or production data was changed.

## Decision summary

Move invoice records and queue state to PostgreSQL, keep Supabase Auth, and create separate Supabase projects for staging and production. Use a private Supabase Storage bucket in each project for original invoices and generated workbooks. The API and worker must use environment-specific Supabase credentials and durable object keys, never container paths.

Keep object backups independent of database backups. Supabase’s daily PostgreSQL backups do not contain Storage objects. Before production migration, configure and restore-test a second copy of every object in a separately controlled backup destination. The Voroa Object Storage bucket is a possible low-cost second copy, but its own files have no provider backup, version recovery, or undo; it cannot be the only recovery copy.

This document does not approve or perform the production cutover.

## Scope and evidence limits

I inspected the checked-out repository and local SQLite files read-only. I did not access Voroa, Supabase, production credentials, deployment settings, or customer records. The local checkout contains two application database files; each showed 6 invoices, 15 line items, and 18 jobs during read-only inspection. Those are **local checkout counts**, not production counts. No staging application or staging project was available, so staging tests have not been executed.

Provider rates below are published list prices checked on 6 November 2026. Your current workspace plan, compute sizes, usage, tax treatment, and Supabase organization billing are unknown, so the formulas and stated assumptions are part of each estimate.

## Phase 1 — Storage dependency map

### Databases and tables

| Location | Tables | Role |
|---|---|---|
| invoice_engine.db (default path, overrideable with DATABASE_PATH) | invoices, line_items, jobs, internal SQLite sqlite_sequence | Active app and worker state when run from the repository/container working directory |
| invoice_engine_backup.db | Same three application tables in the inspected local copy | Local backup artifact; not verified as a production backup |
| tmpj9e6m0rd/test.sqlite3, tmpcsz4cuui/test.sqlite3 | Test databases created by the tenant-security tests | Temporary test artifacts, not app data |
| database(1).py | Defines invoices and line_items | Legacy duplicate implementation; active app imports database.py, not this file |
| Supabase public.user_workspaces | One row per owner_id, retail_state JSONB, business_settings JSONB, updated_at | Existing retail/sales/purchase/customer state and bill settings; RLS policies restrict authenticated users to their own row |
| Supabase Auth schema | Supabase-managed Auth data | Sign-in and user identity; preserve this service |

The SQLite invoice schema has invoice headers plus tenant owner_id; line items reference invoice IDs with cascade delete. Monetary and quantity fields use SQLite REAL. The jobs table has UUID text IDs, filename/hash, owner, status, attempts, error and timestamps. SQLite also has indexes and an internal sequence table. There is no current PostgreSQL invoice/job schema and no Supabase Storage bucket integration in the application.

The workspace migration file is supabase_workspace_migration.sql. It creates user_workspaces with row-level security. It does not migrate invoices or jobs.

### Read and write paths

- api.py initializes the invoice database and job table at startup. Authenticated invoice list/search, invoice detail and stats routes read from invoices and line_items. Job listing/status and download routes read jobs. POST /upload writes the incoming file to uploads/, hashes it, and inserts a pending row into jobs.
- worker.py polls jobs, marks work processing/completed/failed, retries failures, reads the upload, checks duplicates, calls document extraction, saves invoice headers and line items, and creates the XLSX output.
- batch_processor.py is also a standalone/CLI path: it scans samples/, processes documents, saves invoice records and generates a workbook. It is not the HTTP upload queue path.
- database(1).py is a duplicate legacy database implementation and does not appear in active imports.
- frontend/supabase-config.js and the frontend Supabase client use Supabase Auth and user_workspaces. Retail state and business/bill settings are stored as JSONB there. The API validates bearer tokens through Supabase Auth using the project URL and public/anon key; it does not currently connect to Supabase Postgres using a service-role key.

### Files and local path assumptions

| Path or mechanism | Contents and dependency |
|---|---|
| uploads/ | Original PDFs/images from API uploads. Jobs store a filename, and the worker later reads this local path. |
| outputs/{job_id}.xlsx | Generated job export; status/download routes check this path and return it with FileResponse. |
| batch_processed_invoices.xlsx in the working directory | Temporary/final workbook path used by batch_processor.py; the worker moves it into outputs/. |
| samples/ | Input files for manual/standalone batch processing and examples. |
| processed_invoices.xlsx, processed_invoice.xlsx | Fixed working-directory exports from standalone document_loader.py and ocr_to_excel.py. |
| Browser downloads | Dashboard SheetJS exports are created and downloaded in the user’s browser; not persisted by the server. Retail bill PDF output uses browser print/save as PDF, not a backend PDF store. |
| Container working directory | SQLite default path and the relative uploads/, outputs/, sample and workbook paths depend on it. A Voroa service’s local disk is temporary; a redeploy can remove it. |

The OCR pipeline and duplicate detector require a filesystem path. The worker therefore depends on original uploads being present when it processes a queued job. The generated workbook is also needed later by the API download route. The Docker command runs the worker and API in one container today; splitting them would require both processes to share PostgreSQL and object storage rather than a shared local directory.

## Phase 2 — Database options

| Option | Cost and limits | Backup / compatibility | Security, isolation and operations |
|---|---|---|---|
| **A. Reuse the existing Supabase production project for staging** | Lowest incremental cost. Existing plan/usage unknown. | PostgreSQL is compatible with the new relational schema. Existing Pro projects have daily database backups, but database backups exclude Storage objects. | Reject for staging data: separate schemas or table prefixes would still share project credentials, Auth users, Storage, quotas and blast radius. A staging bug could reach production data. |
| **B. Separate Supabase staging and production projects** | Pro organization: $25/month base, first Micro compute included; another Micro project starts at $10/month. **Two Micro projects estimate: $35/month total before tax/overages**, assuming both projects are under one Pro org. If production already pays the $25 plan, staging adds about $10/month. Two separate Pro organizations would start around $50/month with one Micro each. | Real PostgreSQL with JSONB and SQL; daily backups on Pro (confirm they are enabled), 7-day retention. Micro lists 60 direct and 200 pooled connections. Use the Supavisor pooler and small app pools. | Recommended. Separate project URL, database, Auth users, Storage buckets and API keys isolate stage from prod. RLS can use auth.uid() when queries carry the user JWT. A server database role that bypasses RLS would still need strict owner filters in every API query. More than one project adds small operational overhead. |
| **C. Voroa Managed PostgreSQL** | Current list: DB Nano ₹0 (256 MB RAM, 100 connections, 1 GB); Starter ₹299/mo (1 GB RAM, 1 GB); Basic ₹499/mo (1 GB RAM, 5 GB); Standard ₹999/mo (2 GB RAM, 10 GB); Pro ₹1,499/mo (4 GB RAM, 10 GB), all plus 18% GST. Extra DB storage ₹21/GB/mo. Free DB size does not include the advertised paid-size daily backups. Verify that nightly backups are enabled and confirm restore retention before relying on them. | PostgreSQL 16/17/18, JSONB, and relational constraints are compatible. Paid sizes advertise daily backups and PITR, with retention depending on Voroa workspace plan. | Keeps app and DB in Voroa, but Supabase Auth remains a separate identity provider. The app would validate the Supabase JWT and enforce tenant filters itself; Supabase-native auth.uid() RLS is unavailable in that database without a carefully maintained JWT-to-session bridge. This adds cross-provider failure modes and security work. |

**Recommendation: B.** It preserves the current Auth provider and keeps Auth, PostgreSQL, RLS and object permissions in one project per environment. Do not place stage data in the production project. Use a separate test Auth user set in staging. Select a paid Pro organization for production and staging if the 7-day daily DB backup window is the minimum acceptable baseline. Add a tested off-provider database export because a project deletion also removes its provider-held backups.

Published prices: [Supabase pricing](https://supabase.com/pricing), [Supabase backup terms](https://supabase.com/docs/guides/platform/backups), and [Voroa PostgreSQL pricing and recovery notes](https://getvoroa.com/pricing/).

## Phase 3 — Object storage

| Option | Price and transfer | Permissions and SDK | Recovery |
|---|---|---|---|
| **Supabase Storage (recommended primary)** | Pro lists 100 GB file storage and 250 GB uncached egress plus 250 GB cached egress; excess storage is $0.0213/GB-month, uncached egress $0.09/GB and cached egress $0.03/GB. There is no separate fixed bucket charge within quota. Confirm how the organization’s quota is metered before launch. | Private buckets, Postgres RLS policies, Supabase JS SDK / Storage API, S3-compatible access, and expiring signed URLs. Keep the invoice bucket private; authorize owner before issuing a short-lived download URL. | Database backups do not back up object bytes. Published Storage docs do not promise automatic object versioning or deleted-object recovery. Signed URLs cannot individually be revoked; deleting, moving or renaming an object invalidates that object’s URLs. Maintain an independent object copy and restore test. |
| **Voroa Object Storage** | S-20: 20 GB, 100 GB transfer, 25,000 uploads and 300,000 downloads for ₹99/month + GST (₹116.82 including 18% GST). Excess storage ₹4/GB-month and transfer ₹1/GB. Request allowance is fair use; excess requests are refused. S-50 ₹199, S-100 ₹399, then larger tiers. Two S-20 buckets (stage + prod) total ₹198 + GST = ₹233.64/month. | S3 API works with Python boto3 and other S3 tools. Configure endpoint, bucket and secret environment variables; docs specify region auto and path-style addressing. Dashboard download links expire after 1 hour, 1 day or 7 days. S3 presigned URL behavior should be proven with the exact SDK in staging; do not use a share link for customer data. | Voroa states files are not backed up and deleted files/buckets cannot be restored. No object versioning or soft-delete guarantee is documented. India location is not guaranteed; the service says Asia-Pacific best effort. |

**Recommendation:** use private Supabase Storage buckets as the application’s primary store because its Auth/RLS integration supports tenant isolation and separate projects give a clean stage/prod boundary. Keep a separately controlled backup copy, with dated keys or versioning at the backup destination, and verify restore. The current published Voroa bucket service is suitable for a low-cost staging compatibility trial or an extra copy, but its documented recovery limits make it unsuitable as the sole production copy.

Provider references: [Supabase Storage pricing](https://supabase.com/docs/guides/storage/pricing), [Storage access control](https://supabase.com/docs/guides/storage/security/access-control), [signed URLs](https://supabase.com/docs/guides/storage/serving/downloads), [Voroa Object Storage docs](https://getvoroa.com/docs/object-storage/), and [Voroa pricing](https://getvoroa.com/pricing/).

## Cost estimate and required infrastructure

### Known monthly baseline

| Component | Estimate |
|---|---:|
| Supabase Pro, production + separate staging project, one Micro per project under one org | **$35/month before tax and usage overages** |
| If the production Pro plan is already paid | **About $10/month incremental** for a second Micro project |
| Supabase storage | $0 extra while under listed plan quota; overage rates above |
| Voroa Object Storage (not selected as primary) | ₹116.82/month incl. GST per S-20 bucket; ₹233.64 for two |
| Voroa staging app service | Nano is listed as free but only 512 MB RAM; Nano Plus ₹149 + GST (₹175.82 incl. GST) or Starter ₹298 + GST (₹351.64 incl. GST). OCR memory and current production size must determine the actual tier. |
| Voroa workspace plan | Free ₹0 or Growth ₹499 + GST (₹589 incl. GST); account’s present plan is unknown. |

The $35 figure is an exact list-price calculation for the stated Supabase assumption, not a quote from your account. It excludes any compute size above Micro, usage overages, tax, backup destination, and Voroa service/workspace charges. I cannot give one exact all-in monthly bill without your project/org plan, region, data size, traffic, current app size and billing view.

### Required before staging starts

1. Create a new Supabase staging project. Keep production’s project unchanged.
2. Use a distinct Voroa staging application deployment/service, separate environment variables and staging URL. Use a separate project/service identity and test-only credentials.
3. Create a private invoice bucket inside the staging project; production gets a separate private bucket only in a later approved release phase.
4. Add staging-only Supabase URL and publishable key to the staging frontend build. The publishable key is public, but the URL/key must point to staging. Do not copy production DB passwords, service-role keys, object keys, Mistral secrets, OAuth secrets or customer data into staging.
5. Create two staging-only Supabase test users. Add staging-only model/API credentials if OCR processing needs an external model; cap or monitor spend.
6. Create database schema and RLS policies in staging first. Use owner ID as UUID referencing that project’s auth.users. Test isolation against both API routes and Storage reads/writes.
7. Use TLS, narrow environment secrets, a pooled PostgreSQL connection, and a small API/worker pool sized below the selected project limit. No DB or storage secret belongs in browser code.
8. Set staging CORS to the staging origin. Restrict production CORS separately during a future production change.
9. Configure the independent object backup process and test a restore before production readiness.

No cloud resource was created in this task.

## Phase 5 — Repeatable migration design

Implement and run this only against a separately provisioned staging source/destination first.

### Database migration

1. **Read-only inventory.** Capture SQLite schema version, table counts, owner/null-owner counts, invoice-to-line-item counts, job states and foreign-key check results. Record every source file and database size/hash.
2. **Original snapshots.** Pause the worker and uploads for a consistent snapshot. Use SQLite’s online backup mechanism (so WAL state is included); copy the SQLite database, any WAL/SHM files needed for forensic retention, and all uploads/ and outputs/ files to a separate protected backup location. Hash each snapshot. Never overwrite or delete originals.
3. **Create PostgreSQL schema.** Define versioned SQL migrations for invoices, line items, jobs and file references. Use UUID-compatible owner IDs, explicit foreign keys and indexes, NUMERIC for currency values, timestamps with time zone where appropriate, and RLS policies. Preserve source identifiers where feasible or write a durable old-ID-to-new-ID map. Decide how to preserve REAL values without silently rounding invoice totals.
4. **Resolve tenant ownership.** Report rows with missing/ambiguous owner_id separately. Do not automatically assign all legacy records to one account. Confirm the correct owner before inserting any such record.
5. **Idempotent load.** Import parent invoices, then line items through the ID map, then jobs. Use a migration-run ID and stable source keys so reruns update/skip already imported rows rather than duplicate them. Keep job status and timestamps.
6. **Compare.** Compare per-table source and target counts, null owner counts, IDs or mapping counts, line-item counts per invoice, monetary totals by currency, job-state counts, and foreign-key orphans. Produce a signed/checksummed migration report. Differences must be explained before cutover.
7. **Duplicate handling.** Inventory duplicate file hashes before adding constraints. The current SQLite invoices.file_hash is globally unique. New tenant-aware dedupe should use (owner_id, file_hash) after resolving legacy rows; do not silently drop records that share a hash.

### File migration and reference update

1. Generate a manifest of every original under uploads/, every generated XLSX under outputs/, the temporary workbook where present, and every file path referenced by a job. Include source path, byte size, SHA-256, job ID, owner ID, role (original/export/temp), and whether a DB row references it.
2. Report missing references, missing files, orphan files and hash duplicates before upload. No migration may pass with an unexplained missing original.
3. Upload to the staging bucket using opaque deterministic keys such as tenant/{owner_id}/invoices/{job_id}/original.{ext} and tenant/{owner_id}/jobs/{job_id}/export.xlsx. Avoid user filenames as path segments. Keep buckets private.
4. Re-read each uploaded object and compare byte length and SHA-256 against the manifest. Record destination object key and checksum. Verify counts and report identical content hashes separately; duplicate detection must not merge separate tenants’ objects.
5. Add provider-neutral object-key fields to invoice/job records (for example original_object_key, export_object_key); never persist a signed URL as a permanent reference. Update the staging API and worker to read/write via object-storage SDK and only generate an owner-authorized short-lived link or proxy a download.
6. Repeat the import and manifest check from the same original snapshot. Prove reruns do not create duplicate rows or objects. Retain the source snapshot and files unchanged.

### Production cutover and rollback, reserved for a later approval

A later, separately approved release should use a maintenance window: stop new uploads and worker claims, take final backups, apply the tested schema, migrate the final delta, verify counts and every object hash, switch app environment/config to PostgreSQL and object storage, then run smoke and isolation checks. Keep the original DB/files and an external verified backup read-only for the agreed retention period.

Rollback: put the app back into maintenance mode, preserve the new PostgreSQL and Storage state for diagnosis, then revert the deployment/environment to the prior backend only if its original SQLite/files have been preserved and are usable. If writes occurred after the cutover, reconcile those writes before reopening the old system. Do not delete or overwrite either source or destination during rollback. A SQLite restore alone cannot recover uploads lost from Voroa’s temporary disk; external source snapshots are a prerequisite.

## Phase 6 — Staging verification matrix

The following tests are the acceptance suite to run after staging implementation. They have **not** been run because no isolated staging project, deployment or test credentials were available.

| Test | Procedure | Pass evidence |
|---|---|---|
| 1. Two test users | Create staging users A and B using only staging Auth. | Different staging user IDs; neither account exists in prod Auth. |
| 2. Tenant isolation | A and B each create invoices/jobs/files. Try direct API reads, searches, status lookup, exports, and bucket access using the other user’s token/key. | Each user sees only their rows and objects; cross-user access returns 404/403. Test RLS directly as authenticated as well. |
| 3. Bill settings | A saves and reloads business settings; B has distinct values. | Values persist in separate user_workspaces rows and cannot be read or overwritten cross-account. |
| 4. Sales records | Both users add different sales/customer records to retail_state. | Reload returns each user’s own JSONB state only. |
| 5. Sample invoice upload | A uploads a non-customer sample PDF/image. | Job row and private original object key exist; recorded SHA-256 matches source. |
| 6. Invoice processing | Worker claims the job, reads the object, runs OCR/extraction and saves invoice plus line items. | Job reaches expected state; correct tenant ID, row counts and file checksum recorded. |
| 7. Generated export | Download the generated workbook as A; try as B. | A receives a valid XLSX; B is denied; no public object URL exists. |
| 8. Staging redeploy | Redeploy/restart only staging app and worker. | New process serves the same DB records and object keys; original upload and export still download and hash correctly. |
| 9. Restore rehearsal | Restore staging DB and object backup to a recovery project/bucket. | Restored records and files match pre-backup counts and hashes; document elapsed time and gaps. |

Evidence should include run timestamp, staging commit/build ID, project refs (not credentials), test user IDs, record counts, job IDs, object keys, before/after hashes, access-denial results, and redeploy/restore results.

## Remaining risks and release gates

- **No remote production audit:** production database size/counts, current Voroa disk configuration, object/file inventory and billing cannot be verified from this checkout.
- **Local-only SQLite:** the repo’s default path and relative file locations are not durable. Do not assume a container redeploy preserves them.
- **Legacy ownership:** nullable owner IDs need a reviewed mapping before migration. Incorrect assignment could expose one business’s invoices to another.
- **RLS bypass:** a privileged server connection can bypass Supabase RLS. API tenant predicates must be complete and tested; never put a service-role key in the frontend.
- **Object recovery:** neither the Supabase database backup nor Voroa Object Storage’s published terms provide automatic object restore. Independent copies and restore rehearsal are a hard production gate.
- **No staging results yet:** this is a design/report, not evidence that staging migration or end-to-end processing passes.
- **Documented but dormant paths:** standalone scripts and copied/legacy files still assume local filesystem paths. Confirm whether they are shipped or used operationally; either migrate them or explicitly retire them before release.

## Source references

- [Voroa Object Storage documentation](https://getvoroa.com/docs/object-storage/)
- [Voroa service disk documentation](https://getvoroa.com/docs/service-disk/)
- [Voroa current pricing](https://getvoroa.com/pricing/)
- [Voroa Managed PostgreSQL](https://getvoroa.com/managed-postgresql-india/)
- [Supabase pricing](https://supabase.com/pricing)
- [Supabase Storage pricing](https://supabase.com/docs/guides/storage/pricing)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
- [Supabase signed URLs](https://supabase.com/docs/guides/storage/serving/downloads)
- [Supabase database backups](https://supabase.com/docs/guides/platform/backups)

