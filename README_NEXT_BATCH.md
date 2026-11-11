# Invoice Engine — Working Bundle (not final)

This is the combined working bundle after receiving the next file batch. It includes the current dashboard, an updated landing page, the uploaded authentication and Supabase config files, worker and validator files, and four new 45-second narrated tutorials.

## Tutorial files
- `frontend/tutorials/invoice-engine-overview.mp4`
- `frontend/tutorials/invoice-engine-purchasing.mp4`
- `frontend/tutorials/invoice-engine-billing.mp4`
- `frontend/tutorials/invoice-engine-sales.mp4`
- `frontend/tutorials/posters/` contains their poster images.
- `frontend/tutorials/TUTORIAL_SCRIPTS.md` contains the narration scripts.
- The previous 10-second tutorial is preserved at `frontend/tutorials/archive/original-10-second-tutorial.mp4`.

## Before use
This is a working bundle, not a verified production release. Keep a backup of your original project and database files. The backend has not yet been fully integration-tested. In particular, `worker.py` imports `database.py`, while the supplied database module in the received files is named `database(1).py`; do not deploy until that mismatch and the project dependencies are reconciled. Billing and Sales tutorials describe the intended workflows and explicitly note where integration/configuration must be verified.

## Configuration and security
- Do not add API keys or passwords to the ZIP.
- `supabase-config.js` contains a Supabase URL and publishable key. Keep server-side secrets private and use environment variables for them.
- Test authentication, API connectivity, Purchasing extraction, and the export flow before deploying.
