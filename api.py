from pathlib import Path
import hashlib
import shutil

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import (
    initialize_database,
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

UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("outputs")
FRONTEND_FOLDER = Path("frontend")

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)


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
# SUPPORTED FILES
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}


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

    return {
        "status": "healthy"
    }


# ============================================================
# SYSTEM INFO
# ============================================================

@app.get("/system")
def system_info():

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
        # Prevent filename collisions
        # ----------------------------------------------------

        file_name = original_name

        file_path = (
            UPLOAD_FOLDER
            / file_name
        )

        # If the same filename already exists,
        # create a unique filename.

        if file_path.exists():

            stem = Path(
                original_name
            ).stem

            suffix = Path(
                original_name
            ).suffix

            counter = 1

            while file_path.exists():

                file_name = (
                    f"{stem}_{counter}"
                    f"{suffix}"
                )

                file_path = (
                    UPLOAD_FOLDER
                    / file_name
                )

                counter += 1

        # ----------------------------------------------------
        # Save uploaded file
        # ----------------------------------------------------

        with open(
            file_path,
            "wb",
        ) as buffer:

            shutil.copyfileobj(
                uploaded_file.file,
                buffer,
            )

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

):

    return search_invoices(

        page=page,

        page_size=page_size,

    )


# ============================================================
# SINGLE INVOICE
# ============================================================

@app.get("/invoices/{invoice_id}")
def invoice_details(
    invoice_id: int,
):

    invoice = get_invoice_by_id(
        invoice_id
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
def statistics():

    return get_database_stats()


# ============================================================
# JOB STATUS
# ============================================================

@app.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
):

    job = get_job(
        job_id
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
):

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