import time
from pathlib import Path

from job_queue import (
    initialize_jobs_table,
    get_pending_jobs,
    mark_job_processing,
    mark_job_completed,
    mark_job_failed,
    retry_job,
    get_job,
)

from batch_processor import (
    process_document,
    create_excel,
)

from duplicate_detector import (
    calculate_file_hash,
)

from database import (
    initialize_database,
    invoice_exists,
    get_invoice_by_hash,
    save_invoice,
)


UPLOAD_FOLDER = Path("uploads")
OUTPUT_FOLDER = Path("outputs")

MAX_ATTEMPTS = 3

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)


def create_job_excel(invoice, job_id):

    output_file = (
        OUTPUT_FOLDER
        / f"{job_id}.xlsx"
    )

    temporary_output = Path(
        "batch_processed_invoices.xlsx"
    )

    if temporary_output.exists():
        temporary_output.unlink()

    excel_created = create_excel(
        [invoice],
        []
    )

    if not excel_created:
        raise RuntimeError(
            "Excel generation failed."
        )

    if not temporary_output.exists():
        raise FileNotFoundError(
            "Excel generation reported success, "
            "but batch_processed_invoices.xlsx "
            "was not created."
        )

    if output_file.exists():
        output_file.unlink()

    temporary_output.replace(
        output_file
    )

    if not output_file.exists():
        raise FileNotFoundError(
            f"Excel file was not created: "
            f"{output_file}"
        )

    return output_file


def process_job(job):

    job_id = job["id"]
    file_name = job["file_name"]

    print()
    print("=" * 50)
    print("INVOICE ENGINE WORKER")
    print("=" * 50)

    print(
        f"Job: {job_id}"
    )

    print(
        f"File: {file_name}"
    )

    print(
        f"Attempt: {job['attempts'] + 1}"
    )

    file_path = (
        UPLOAD_FOLDER
        / file_name
    )

    mark_job_processing(
        job_id
    )

    print(
        "Status: processing"
    )

    try:

        if not file_path.exists():

            raise FileNotFoundError(
                f"Uploaded file not found: "
                f"{file_path}"
            )

        file_hash = (
            calculate_file_hash(
                file_path
            )
        )

        if invoice_exists(
            file_hash
        ):

            print(
                "Invoice already exists "
                "in database."
            )

            invoice = (
                get_invoice_by_hash(
                    file_hash
                )
            )

            if invoice is None:

                raise RuntimeError(
                    "Invoice exists but "
                    "could not be retrieved."
                )

            print(
                "Using existing invoice data."
            )

        else:

            print(
                "Running Invoice Engine..."
            )

            invoice = (
                process_document(
                    file_path
                )
            )

            print(
                "OCR + AI + normalization "
                "+ validation complete."
            )

            save_invoice(
                invoice,
                file_hash
            )

            print(
                "Invoice saved to database."
            )

        output_file = (
            create_job_excel(
                invoice,
                job_id
            )
        )

        print(
            f"Excel created: "
            f"{output_file}"
        )

        mark_job_completed(
            job_id
        )

        print(
            "Status: completed"
        )

    except Exception as error:

        print(
            f"Job failed: {error}"
        )

        retry_job(
            job_id
        )

        updated_job = get_job(
            job_id
        )

        if (
            updated_job is not None
            and updated_job["attempts"]
            >= MAX_ATTEMPTS
        ):

            mark_job_failed(
                job_id,
                error
            )

            print(
                "Maximum attempts reached."
            )

            print(
                "Status: failed"
            )

        else:

            print(
                "Status: retrying"
            )


def run_worker():

    initialize_database()

    initialize_jobs_table()

    print(
        "Invoice Engine Worker started."
    )

    while True:

        jobs = get_pending_jobs(
            limit=1
        )

        if not jobs:

            print(
                "No pending jobs. "
                "Worker waiting..."
            )

            time.sleep(3)

            continue

        for job in jobs:

            process_job(
                job
            )


if __name__ == "__main__":

    run_worker()