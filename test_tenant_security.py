"""Regression checks for user-scoped invoice and job access."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import api
import job_queue
from auth import get_current_user
from fastapi import HTTPException


class TenantSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test.sqlite3"
        self.database_path_patch = patch.object(database, "DATABASE_FILE", db_path)
        self.jobs_path_patch = patch.object(job_queue, "DATABASE_FILE", db_path)
        self.database_path_patch.start()
        self.jobs_path_patch.start()
        database.initialize_database()
        job_queue.initialize_jobs_table()

    def tearDown(self):
        self.jobs_path_patch.stop()
        self.database_path_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def invoice(file_name):
        return {
            "file_name": file_name,
            "invoice_number": file_name,
            "status": "Valid",
            "total_amount": 100,
            "line_items": [{"description": "Item", "quantity": 1, "amount": 100}],
        }

    def test_invoices_and_aggregates_are_scoped_to_owner(self):
        user_a_id = database.save_invoice(self.invoice("a.pdf"), "hash-a", "user-a")
        database.save_invoice(self.invoice("b.pdf"), "hash-b", "user-b")

        results = database.search_invoices(owner_id="user-a")
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["results"][0]["file_name"], "a.pdf")
        self.assertIsNone(database.get_invoice_by_id(user_a_id, owner_id="user-b"))
        self.assertEqual(database.get_database_stats(owner_id="user-a")["total_invoices"], 1)
        self.assertEqual(database.get_database_stats(owner_id="user-a")["total_line_items"], 1)

    def test_legacy_hash_stays_deduplicated_only_for_its_owner(self):
        database.save_invoice(self.invoice("legacy.pdf"), "legacy-content-hash", "user-a")
        self.assertTrue(database.invoice_exists("legacy-content-hash", owner_id="user-a"))
        self.assertFalse(database.invoice_exists("legacy-content-hash", owner_id="user-b"))

    def test_jobs_are_scoped_to_owner(self):
        job_id = job_queue.add_job("a.pdf", "file-hash", owner_id="user-a")
        self.assertIsNotNone(job_queue.get_job(job_id, owner_id="user-a"))
        self.assertIsNone(job_queue.get_job(job_id, owner_id="user-b"))

    def test_missing_bearer_token_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            get_current_user(None)
        self.assertEqual(error.exception.status_code, 401)

    def test_sensitive_api_routes_require_server_authentication(self):
        protected_paths = {
            "/system",
            "/upload",
            "/search",
            "/invoices",
            "/invoices/{invoice_id}",
            "/stats",
            "/jobs/{job_id}",
            "/download/{job_id}",
        }
        routes = {route.path: route for route in api.app.routes if hasattr(route, "dependant")}
        for path in protected_paths:
            with self.subTest(path=path):
                dependencies = {dependency.call for dependency in routes[path].dependant.dependencies}
                self.assertIn(get_current_user, dependencies)


if __name__ == "__main__":
    unittest.main()
