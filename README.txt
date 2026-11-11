INVOICE ENGINE — FINANCE MODULE INTEGRATION PATCH
=================================================

This bundle is based on the source files uploaded in this conversation:
- api.py
- database.py
- dashboard(7).html
- Electron main.cjs and package.json

It adds:
1) Bank reconciliation: CSV/XLSX statement upload, normalized transaction storage,
   conservative automatic matching against manually recorded book entries,
   manual matching, reconciliation status and export.
2) Accounting Migration Centre: CSV/XLSX upload, header mapping, preview,
   validation, duplicate detection and explicit commit into a staging ledger.
   It does NOT claim native Tally/BUSY database/API integration. Use authorized
   exports from those systems and map their columns.

IMPORTANT:
- This is an integration patch, not a claim of production-accounting certification.
- Run against a BACKUP / TEST database first.
- All new records are scoped to the authenticated Supabase user ID.
- Reconciliation suggestions do not post journal entries or move money.
- Migration imports into a staging ledger, not directly into the existing sales,
  inventory or statutory books. Review and reconcile before any accounting use.
- CSV/XLSX column layouts vary; the UI provides explicit mapping.
- Never import real customer financial data until your adult project owner has
  reviewed access controls, backups, tax treatment and accounting rules.

Install:
1. Back up your project and database.
2. Copy api.py and database.py from this bundle over the matching project files.
3. Copy finance.html into your project's frontend folder.
4. Add the two sidebar links shown in DASHBOARD-INTEGRATION.txt to the active
   dashboard file (dashboard.html). This keeps the original dashboard intact.
5. Ensure python-multipart and openpyxl are installed (already in your supplied
   requirements.txt according to the uploaded dependency list).
6. Restart API and test with sample data only.

This patch intentionally avoids replacing the user's dashboard wholesale because
several different dashboard snapshots were uploaded and the active deployed
version cannot be proven from the files alone.

TESTS RUN IN THIS BUILD:
- Python syntax compilation: passed for api.py and database.py.
- SQLite initialization: passed; created the four new finance tables alongside
  the existing invoices and line_items tables.
- Inline JavaScript syntax check with Node: passed.

NOT VERIFIED:
- Live Supabase sign-in/API calls (no live credentials/session were exercised).
- Bank statement format compatibility with a real bank's export.
- Tally/BUSY/Marg source-specific export variations.
- Accounting correctness / statutory compliance / production load.
- Installer build or deployment in your Windows environment.
