from pathlib import Path
import hashlib
import csv
import io
import json
from datetime import date, datetime
import os
import re
import uuid

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query,
    Depends,
    Form,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from auth import get_current_user

from database import (
    initialize_database,
    get_connection,
    search_invoices,
    get_invoice_by_id,
    get_database_stats,
)

from job_queue import (
    initialize_jobs_table,
    add_job,
    get_job,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Invoice Engine API",
    version="2.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# FOLDERS
# ============================================================

DATA_FOLDER = Path(os.environ.get("INVOICE_ENGINE_DATA_DIR", ".")).resolve()
UPLOAD_FOLDER = DATA_FOLDER / "uploads"
OUTPUT_FOLDER = DATA_FOLDER / "outputs"
FRONTEND_FOLDER = Path(__file__).resolve().parent / "frontend"

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# STATIC FRONTEND
# ============================================================

if FRONTEND_FOLDER.exists():

    app.mount(
        "/frontend",
        StaticFiles(
            directory=FRONTEND_FOLDER
        ),
        name="frontend",
    )




# ============================================================
# FINANCE MODULES: BANK RECONCILIATION + MIGRATION CENTRE
# ============================================================

def _owner(user: dict) -> str:
    return str(user["id"])


def _read_tabular_upload(filename: str, content: bytes) -> list[dict]:
    """Read CSV or XLSX into dictionaries without executing spreadsheet formulas."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=400, detail="Upload a .csv or .xlsx file.")
    try:
        if suffix == ".csv":
            text = content.decode("utf-8-sig")
            return list(csv.DictReader(io.StringIO(text)))
        from openpyxl import load_workbook
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        values = sheet.iter_rows(values_only=True)
        headers = next(values, None)
        if not headers:
            return []
        names = [str(value).strip() if value is not None else "" for value in headers]
        return [
            {names[i]: row[i] for i in range(min(len(names), len(row))) if names[i]}
            for row in values
            if any(value is not None for value in row)
        ]
    except (UnicodeDecodeError, csv.Error, ValueError, OSError) as error:
        raise HTTPException(status_code=400, detail=f"Could not read tabular file: {error}") from error


def _number(value, field_name: str) -> float:
    if value is None or str(value).strip() == "":
        return 0.0
    try:
        cleaned = str(value).replace(",", "").replace("₹", "").strip()
        result = float(cleaned)
        if not __import__("math").isfinite(result):
            raise ValueError()
        return round(result, 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid numeric value in {field_name}: {value}")


def _iso_date(value) -> str:
    if value is None or str(value).strip() == "":
        raise HTTPException(status_code=400, detail="A transaction date is required.")
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    raw = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported date format: {raw}")


@app.get("/finance/bank/transactions")
def finance_bank_transactions(user: dict = Depends(get_current_user)):
    owner = _owner(user)
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT b.*, e.entry_date AS matched_date, e.description AS matched_description,
                      e.amount AS matched_amount, e.direction AS matched_direction
               FROM bank_transactions b
               LEFT JOIN book_entries e ON e.id=b.matched_entry_id
               WHERE b.owner_id=? ORDER BY b.txn_date DESC, b.id DESC""", (owner,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.post("/finance/bank/import")
async def finance_bank_import(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    content = await file.read()
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Statement must be smaller than 12 MB.")
    rows = _read_tabular_upload(file.filename, content)
    if not rows:
        raise HTTPException(status_code=400, detail="The statement has no data rows.")
    owner = _owner(user)
    connection = get_connection()
    inserted, duplicates = 0, 0
    try:
        for index, row in enumerate(rows, start=2):
            normalized = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
            def pick(*keys):
                return next((normalized[k] for k in keys if k in normalized and normalized[k] not in (None, "")), None)
            txn_date = _iso_date(pick("date", "transaction date", "txn date", "value date"))
            description = str(pick("description", "narration", "particulars", "details", "remarks") or "").strip()
            if not description:
                raise HTTPException(status_code=400, detail=f"Missing description on statement row {index}.")
            debit = _number(pick("debit", "withdrawal", "withdrawals", "dr"), "debit")
            credit = _number(pick("credit", "deposit", "deposits", "cr"), "credit")
            if debit < 0 or credit < 0 or (debit and credit):
                raise HTTPException(status_code=400, detail=f"Row {index}: use non-negative debit OR credit, not both.")
            balance_value = pick("balance", "closing balance")
            balance = None if balance_value in (None, "") else _number(balance_value, "balance")
            ref = str(pick("reference", "ref", "reference no", "transaction id", "cheque no") or "")
            signature = hashlib.sha256(f"{owner}|{txn_date}|{description}|{debit:.2f}|{credit:.2f}|{ref}".encode()).hexdigest()
            cursor = connection.execute(
                """INSERT OR IGNORE INTO bank_transactions
                   (owner_id, statement_ref, txn_date, description, debit, credit, balance)
                   VALUES (?,?,?,?,?,?,?)""",
                (owner, signature, txn_date, description, debit, credit, balance)
            )
            if cursor.rowcount:
                inserted += 1
            else:
                duplicates += 1
        connection.commit()
        return {"inserted": inserted, "duplicates_skipped": duplicates, "total_rows": len(rows)}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.post("/finance/bank/book-entry")
def finance_add_book_entry(payload: dict, user: dict = Depends(get_current_user)):
    owner = _owner(user)
    entry_date = _iso_date(payload.get("date"))
    description = str(payload.get("description") or "").strip()
    direction = str(payload.get("direction") or "").lower()
    amount = _number(payload.get("amount"), "amount")
    if not description or direction not in {"debit", "credit"} or amount <= 0:
        raise HTTPException(status_code=400, detail="Provide description, debit/credit direction and a positive amount.")
    connection = get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO book_entries(owner_id,entry_date,description,amount,direction,reference) VALUES(?,?,?,?,?,?)",
            (owner, entry_date, description, amount, direction, str(payload.get("reference") or "")[:120])
        )
        connection.commit()
        return {"id": cursor.lastrowid, "status": "created"}
    finally:
        connection.close()


@app.get("/finance/bank/book-entries")
def finance_book_entries(user: dict = Depends(get_current_user)):
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM book_entries WHERE owner_id=? ORDER BY entry_date DESC,id DESC",
            (_owner(user),)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.post("/finance/bank/{transaction_id}/match")
def finance_match_bank_transaction(transaction_id: int, payload: dict, user: dict = Depends(get_current_user)):
    owner = _owner(user)
    entry_id = payload.get("book_entry_id")
    connection = get_connection()
    try:
        bank = connection.execute(
            "SELECT * FROM bank_transactions WHERE id=? AND owner_id=?", (transaction_id, owner)
        ).fetchone()
        entry = connection.execute(
            "SELECT * FROM book_entries WHERE id=? AND owner_id=?", (entry_id, owner)
        ).fetchone()
        if not bank or not entry:
            raise HTTPException(status_code=404, detail="Bank transaction or book entry not found in your workspace.")
        if bank["match_status"] == "matched":
            raise HTTPException(status_code=409, detail="This bank transaction is already matched. Unmatch it before changing the match.")
        already_linked = connection.execute(
            "SELECT 1 FROM bank_transactions WHERE matched_entry_id=? AND owner_id=? AND id<>? LIMIT 1",
            (entry_id, owner, transaction_id),
        ).fetchone()
        if already_linked:
            raise HTTPException(status_code=409, detail="This book entry is already matched to another bank transaction.")
        bank_amount = bank["debit"] if bank["debit"] else bank["credit"]
        if abs(float(bank_amount) - float(entry["amount"])) > 0.01:
            raise HTTPException(status_code=400, detail="Amounts do not match. Resolve the difference before matching.")
        if (bank["debit"] > 0 and entry["direction"] != "debit") or (bank["credit"] > 0 and entry["direction"] != "credit"):
            raise HTTPException(status_code=400, detail="Debit/credit direction does not match.")
        connection.execute(
            "UPDATE bank_transactions SET matched_entry_id=?,match_status='matched' WHERE id=? AND owner_id=?",
            (entry_id, transaction_id, owner)
        )
        connection.commit()
        return {"status": "matched"}
    finally:
        connection.close()


@app.post("/finance/bank/{transaction_id}/unmatch")
def finance_unmatch_bank_transaction(transaction_id: int, user: dict = Depends(get_current_user)):
    connection = get_connection()
    try:
        cursor = connection.execute(
            "UPDATE bank_transactions SET matched_entry_id=NULL,match_status='unmatched' WHERE id=? AND owner_id=?",
            (transaction_id, _owner(user))
        )
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="Transaction not found.")
        connection.commit()
        return {"status": "unmatched"}
    finally:
        connection.close()


@app.get("/finance/migration/batches")
def finance_migration_batches(user: dict = Depends(get_current_user)):
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM migration_batches WHERE owner_id=? ORDER BY created_at DESC",
            (_owner(user),)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


@app.post("/finance/migration/preview")
async def finance_migration_preview(
    file: UploadFile = File(...),
    source_system: str = Form("Generic CSV/Excel export"),
    date_column: str = Form("date"),
    account_column: str = Form("account"),
    description_column: str = Form("description"),
    debit_column: str = Form("debit"),
    credit_column: str = Form("credit"),
    reference_column: str = Form("reference"),
    user: dict = Depends(get_current_user),
):
    content = await file.read()
    if len(content) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Migration file must be smaller than 12 MB.")
    rows = _read_tabular_upload(file.filename, content)
    if not rows:
        raise HTTPException(status_code=400, detail="The export has no data rows.")
    owner = _owner(user)
    batch_id = str(uuid.uuid4())
    connection = get_connection()
    ready, errors = 0, []
    try:
        connection.execute(
            "INSERT INTO migration_batches(id,owner_id,source_system,filename,total_rows) VALUES(?,?,?,?,?)",
            (batch_id, owner, source_system[:80], Path(file.filename or "upload").name[:180], len(rows))
        )
        for number, raw in enumerate(rows, start=2):
            row = {str(k).strip().lower(): v for k, v in raw.items() if k is not None}
            try:
                def col(name):
                    return row.get(str(name).strip().lower())
                txn_date = _iso_date(col(date_column))
                account = str(col(account_column) or "").strip()
                desc = str(col(description_column) or account).strip()
                debit = _number(col(debit_column), "debit")
                credit = _number(col(credit_column), "credit")
                if not account:
                    raise ValueError("Account/ledger name is missing.")
                if debit < 0 or credit < 0 or (debit and credit):
                    raise ValueError("Use non-negative debit OR credit.")
                raw_json = json.dumps(raw, default=str, ensure_ascii=False)
                row_hash = hashlib.sha256(f"{owner}|{batch_id}|{number}|{raw_json}".encode()).hexdigest()
                connection.execute(
                    """INSERT INTO migration_rows
                       (batch_id,owner_id,row_number,record_type,record_date,account_name,reference,debit,credit,raw_json,row_hash,status)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (batch_id, owner, number, "ledger", txn_date, account,
                     str(col(reference_column) or "")[:160], debit, credit, raw_json, row_hash, "ready")
                )
                ready += 1
            except Exception as error:
                errors.append({"row": number, "error": str(error)})
        connection.execute(
            "UPDATE migration_batches SET status='preview', imported_rows=0 WHERE id=? AND owner_id=?",
            (batch_id, owner)
        )
        connection.commit()
        preview = connection.execute(
            "SELECT row_number,record_date,account_name,reference,debit,credit,status FROM migration_rows WHERE batch_id=? AND owner_id=? ORDER BY row_number LIMIT 100",
            (batch_id, owner)
        ).fetchall()
        return {"batch_id": batch_id, "source_system": source_system, "total_rows": len(rows),
                "ready_rows": ready, "error_rows": errors, "preview": [dict(x) for x in preview]}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.post("/finance/migration/{batch_id}/commit")
def finance_migration_commit(batch_id: str, user: dict = Depends(get_current_user)):
    owner = _owner(user)
    connection = get_connection()
    try:
        batch = connection.execute(
            "SELECT * FROM migration_batches WHERE id=? AND owner_id=?", (batch_id, owner)
        ).fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Migration batch not found.")
        if batch["status"] == "committed":
            return {"status": "already_committed", "imported_rows": batch["imported_rows"]}
        ready = connection.execute(
            "SELECT COUNT(*) AS n FROM migration_rows WHERE batch_id=? AND owner_id=? AND status='ready'",
            (batch_id, owner)
        ).fetchone()["n"]
        connection.execute(
            "UPDATE migration_rows SET status='imported' WHERE batch_id=? AND owner_id=? AND status='ready'",
            (batch_id, owner)
        )
        connection.execute(
            "UPDATE migration_batches SET status='committed',imported_rows=? WHERE id=? AND owner_id=?",
            (ready, batch_id, owner)
        )
        connection.commit()
        return {"status": "committed_to_staging_ledger", "imported_rows": ready,
                "note": "Imported records are staged for review; they are not posted to statutory books."}
    finally:
        connection.close()


@app.get("/finance/migration/{batch_id}/rows")
def finance_migration_rows(batch_id: str, user: dict = Depends(get_current_user)):
    connection = get_connection()
    try:
        batch = connection.execute(
            "SELECT id FROM migration_batches WHERE id=? AND owner_id=?", (batch_id, _owner(user))
        ).fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Migration batch not found.")
        rows = connection.execute(
            "SELECT row_number,record_type,record_date,account_name,reference,debit,credit,status FROM migration_rows WHERE batch_id=? AND owner_id=? ORDER BY row_number",
            (batch_id, _owner(user))
        ).fetchall()
        return [dict(x) for x in rows]
    finally:
        connection.close()


# ============================================================
# SUPPORTED FILES
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_FILES_PER_UPLOAD = 20


def _valid_file_signature(extension: str, header: bytes) -> bool:
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    return False


def _stored_upload_name(original_name: str, extension: str) -> str:
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(original_name).stem).strip("_")[:64]
    return f"{uuid.uuid4().hex}_{safe_stem or 'invoice'}{extension}"


# ============================================================
# FILE HASH
# ============================================================

def calculate_file_hash(file_path: Path) -> str:

    sha256 = hashlib.sha256()

    with open(
        file_path,
        "rb",
    ) as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            sha256.update(
                chunk
            )

    return sha256.hexdigest()


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():

    initialize_database()
    initialize_jobs_table()


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    index_file = (
        FRONTEND_FOLDER
        / "index.html"
    )

    if index_file.exists():

        return FileResponse(
            index_file
        )

    return {
        "message": "Invoice Engine API is running",
        "status": "ready",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    connection = None
    try:
        connection = get_connection()
        connection.execute("SELECT 1").fetchone()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database unavailable.") from error
    finally:
        if connection is not None:
            connection.close()
    return {
        "status": "healthy",
        "database": "connected",
    }


# ============================================================
# SYSTEM INFO
# ============================================================

@app.get("/system")
def system_info(user: dict = Depends(get_current_user)):

    stats = get_database_stats()

    return {
        "status": "online",
        "database": "connected",
        "stats": stats,
    }


# ============================================================
# UPLOAD
# ============================================================

@app.post("/upload")
async def upload_invoices(

    # Accept the dashboard's singular "file"
    file: UploadFile | None = File(
        default=None
    ),

    # Also accept the original "files"
    files: list[UploadFile] | None = File(
        default=None
    ),

    user: dict = Depends(get_current_user),

):

    # --------------------------------------------------------
    # Combine both possible upload formats
    # --------------------------------------------------------

    upload_files = []

    if file is not None:

        upload_files.append(
            file
        )

    if files:

        upload_files.extend(
            files
        )

    # --------------------------------------------------------
    # Nothing uploaded
    # --------------------------------------------------------

    if not upload_files:

        raise HTTPException(
            status_code=400,
            detail="No invoice file was uploaded.",
        )

    if len(upload_files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status_code=400, detail=f"Upload at most {MAX_FILES_PER_UPLOAD} files at a time.")

    uploaded_files = []
    jobs_created = []

    # --------------------------------------------------------
    # Process uploaded files
    # --------------------------------------------------------

    for uploaded_file in upload_files:

        if not uploaded_file.filename:

            continue

        original_name = Path(
            uploaded_file.filename
        ).name

        extension = Path(
            original_name
        ).suffix.lower()

        # ----------------------------------------------------
        # Validate extension
        # ----------------------------------------------------

        if extension not in SUPPORTED_EXTENSIONS:

            raise HTTPException(

                status_code=400,

                detail=(
                    f"Unsupported file type: "
                    f"{extension}. "
                    f"Supported types: "
                    f"PDF, PNG, JPG, JPEG."
                ),
            )

        # ----------------------------------------------------
        header = uploaded_file.file.read(16)
        if not _valid_file_signature(extension, header):
            raise HTTPException(status_code=400, detail="File contents do not match the selected PDF or image type.")
        uploaded_file.file.seek(0)

        # Use an opaque server-generated name; never trust client paths or
        # allow two businesses' similarly named uploads to overwrite files.
        file_name = _stored_upload_name(original_name, extension)
        file_path = UPLOAD_FOLDER / file_name
        size = 0
        try:
            with open(file_path, "xb") as buffer:
                while chunk := uploaded_file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Each invoice file must be 25 MB or smaller.")
                    buffer.write(chunk)
        except Exception:
            file_path.unlink(missing_ok=True)
            raise

        # ----------------------------------------------------
        # Calculate hash
        # ----------------------------------------------------

        file_hash = calculate_file_hash(
            file_path
        )

        # ----------------------------------------------------
        # Create processing job
        # ----------------------------------------------------

        job_id = add_job(

            file_name=file_name,

            file_hash=file_hash,
            owner_id=user["id"],

        )

        # ----------------------------------------------------
        # Response information
        # ----------------------------------------------------

        uploaded_files.append(

            {
                "file_name": file_name,

                "job_id": job_id,

                "file_hash": file_hash,

            }

        )

        jobs_created.append(
            job_id
        )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {

        "status": "uploaded",

        "count": len(
            uploaded_files
        ),

        "jobs_created": len(
            jobs_created
        ),

        "files": uploaded_files,

        # Convenient list for frontend use
        "job_ids": jobs_created,

    }


# ============================================================
# SEARCH
# ============================================================

@app.get("/search")
def search(

    q: str | None = Query(
        default=None,
        description=(
            "Search invoice numbers, vendors, "
            "GSTINs, products, models, HSN, "
            "SKUs and filenames."
        ),
    ),

    status: str | None = Query(
        default=None
    ),

    seller_gstin: str | None = Query(
        default=None
    ),

    buyer_gstin: str | None = Query(
        default=None
    ),

    min_amount: float | None = Query(
        default=None
    ),

    max_amount: float | None = Query(
        default=None
    ),

    date_from: str | None = Query(
        default=None
    ),

    date_to: str | None = Query(
        default=None
    ),

    page: int = Query(
        default=1,
        ge=1,
    ),

    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
    ),

    user: dict = Depends(get_current_user),

):

    return search_invoices(

        search_text=q,

        status=status,

        seller_gstin=seller_gstin,

        buyer_gstin=buyer_gstin,

        min_amount=min_amount,

        max_amount=max_amount,

        date_from=date_from,

        date_to=date_to,

        page=page,

        page_size=page_size,
        owner_id=user["id"],

    )


# ============================================================
# ALL INVOICES
# ============================================================

@app.get("/invoices")
def invoices(

    page: int = Query(
        default=1,
        ge=1,
    ),

    page_size: int = Query(
        default=50,
        ge=1,
        le=200,
    ),

    user: dict = Depends(get_current_user),

):

    return search_invoices(

        page=page,

        page_size=page_size,
        owner_id=user["id"],

    )


# ============================================================
# SINGLE INVOICE
# ============================================================

@app.get("/invoices/{invoice_id}")
def invoice_details(
    invoice_id: int,
    user: dict = Depends(get_current_user),
):

    invoice = get_invoice_by_id(
        invoice_id,
        owner_id=user["id"],
    )

    if invoice is None:

        raise HTTPException(

            status_code=404,

            detail="Invoice not found.",

        )

    return invoice


# ============================================================
# STATISTICS
# ============================================================

@app.get("/stats")
def statistics(user: dict = Depends(get_current_user)):

    return get_database_stats(owner_id=user["id"])


# ============================================================
# JOB STATUS
# ============================================================

@app.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    user: dict = Depends(get_current_user),
):

    job = get_job(
        job_id,
        owner_id=user["id"],
    )

    if job is None:

        raise HTTPException(

            status_code=404,

            detail="Job not found.",

        )

    response = {

        "job_id": job["id"],

        "file_name": job["file_name"],

        "status": job["status"],

        "attempts": job["attempts"],

        "error": job["error"],

    }

    # --------------------------------------------------------
    # Check generated Excel
    # --------------------------------------------------------

    output_file = (
        OUTPUT_FOLDER
        / f"{job_id}.xlsx"
    )

    if (

        job["status"] == "completed"

        and output_file.exists()

    ):

        response["download_url"] = (
            f"/download/{job_id}"
        )

    return response


# ============================================================
# DOWNLOAD EXCEL
# ============================================================

@app.get("/download/{job_id}")
def download_excel(
    job_id: str,
    user: dict = Depends(get_current_user),
):

    job = get_job(job_id, owner_id=user["id"])
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    output_file = (
        OUTPUT_FOLDER
        / f"{job_id}.xlsx"
    )

    if not output_file.exists():

        raise HTTPException(

            status_code=404,

            detail=(
                "Excel file is not ready yet."
            ),

        )

    return FileResponse(

        path=output_file,

        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),

        filename=(
            "invoice_results.xlsx"
        ),

    )
