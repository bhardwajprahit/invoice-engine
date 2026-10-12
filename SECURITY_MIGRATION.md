# API authentication and existing invoice data

The dashboard sends the signed-in Supabase access token with API requests. The
API verifies it with Supabase Auth and scopes invoices, statistics, jobs, and
downloads to that Supabase user ID. Do not remove the checks in `api.py` or the
owner filters in `database.py` and `job_queue.py`.

Existing invoices and jobs predate owner scoping and have a null `owner_id`.
They are intentionally hidden from authenticated accounts until their owner is
identified. To assign those records to the existing account, set
`LEGACY_DATA_OWNER_ID` to that account's Supabase Auth user UUID in the server
environment and restart the API and worker once. Startup assigns only rows
whose owner is null. Remove the setting after the migration if you do not want
future ownerless records assigned to that account.

For new deployments, set `DATABASE_PATH` consistently for the API and worker
so both processes use the same SQLite database. The API can read the Supabase
URL and publishable key from `frontend/supabase-config.js`; `SUPABASE_URL` and
`SUPABASE_ANON_KEY` environment overrides are also supported. The publishable
key is intended for client use; never put a Supabase service-role key in the
browser configuration.
