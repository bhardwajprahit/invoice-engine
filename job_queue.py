import sqlite3
import uuid

from pathlib import Path


DATABASE_FILE = Path(
    "invoice_engine.db"
)


MAX_ATTEMPTS = 3

STALE_JOB_MINUTES = 10


def get_connection():

    connection = sqlite3.connect(
        DATABASE_FILE
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


def initialize_jobs_table():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,

            file_name TEXT NOT NULL,

            file_hash TEXT,

            status TEXT NOT NULL
                DEFAULT 'pending',

            attempts INTEGER NOT NULL
                DEFAULT 0,

            error TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            started_at TIMESTAMP,

            completed_at TIMESTAMP
        )
        """
    )

    connection.commit()

    connection.close()


def add_job(
    file_name,
    file_hash=None
):

    connection = get_connection()

    cursor = connection.cursor()

    job_id = str(
        uuid.uuid4()
    )

    cursor.execute(
        """
        INSERT INTO jobs (
            id,
            file_name,
            file_hash,
            status
        )
        VALUES (
            ?, ?, ?, 'pending'
        )
        """,
        (
            job_id,
            file_name,
            file_hash
        )
    )

    connection.commit()

    connection.close()

    return job_id


def recover_stale_jobs():

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            status = 'pending',
            error = 'Worker stopped unexpectedly. Job recovered.',
            started_at = NULL
        WHERE status = 'processing'
        AND started_at < datetime(
            'now',
            ?
        )
        AND attempts < ?
        """,
        (
            f"-{STALE_JOB_MINUTES} minutes",
            MAX_ATTEMPTS
        )
    )

    recovered = cursor.rowcount

    connection.commit()

    connection.close()

    return recovered


def get_pending_jobs(
    limit=10
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE status = 'pending'
        AND attempts < ?
        ORDER BY created_at
        LIMIT ?
        """,
        (
            MAX_ATTEMPTS,
            limit
        )
    )

    jobs = cursor.fetchall()

    connection.close()

    return jobs


def mark_job_processing(
    job_id
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            status = 'processing',
            attempts = attempts + 1,
            started_at =
                CURRENT_TIMESTAMP,
            error = NULL
        WHERE id = ?
        """,
        (
            job_id,
        )
    )

    connection.commit()

    connection.close()


def mark_job_completed(
    job_id
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            status = 'completed',
            completed_at =
                CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            job_id,
        )
    )

    connection.commit()

    connection.close()


def mark_job_failed(
    job_id,
    error
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            status = 'failed',
            error = ?
        WHERE id = ?
        """,
        (
            str(error),
            job_id
        )
    )

    connection.commit()

    connection.close()


def retry_job(
    job_id
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET
            status = 'pending',
            error = NULL,
            started_at = NULL
        WHERE id = ?
        AND attempts < ?
        """,
        (
            job_id,
            MAX_ATTEMPTS
        )
    )

    connection.commit()

    connection.close()


def get_job(
    job_id
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM jobs
        WHERE id = ?
        """,
        (
            job_id,
        )
    )

    job = cursor.fetchone()

    connection.close()

    return job


if __name__ == "__main__":

    initialize_jobs_table()

    recovered = recover_stale_jobs()

    print(
        "Job queue ready."
    )

    print(
        f"Recovered stale jobs: {recovered}"
    )