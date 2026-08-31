"""
tests.test_review_server_gmail — Tests for review_server.py Gmail and Lifecycle endpoints.
"""

import unittest
import json
import io
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock
from review_server import ReviewRequestHandler
from career_os.db.repository import CareerOSRepository


class MockServer:
    def __init__(self, port=8080):
        self.server_port = port


class MockHTTPHandler(ReviewRequestHandler):
    """Subclass of ReviewRequestHandler for headless unit testing without a socket."""
    def __init__(self, request_bytes, method="GET", path="/", port=8080):
        self.server = MockServer(port=port)
        self.rfile = io.BytesIO(request_bytes)
        self.wfile = io.BytesIO()
        self.command = method
        self.path = path
        self.headers = {"Content-Length": str(len(request_bytes))}
        self.request_version = "HTTP/1.1"
        self.close_connection = False

    def send_response(self, code, message=None):
        self.response_code = code

    def send_header(self, keyword, value):
        pass

    def end_headers(self):
        pass


class TestReviewServerGmail(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "server_test.db")
        self.repo = CareerOSRepository(db_path=self.db_path)
        self.repo.init_db()

        self.run_id = self.repo.insert_discovery_run({
            "id": "run_0001",
            "run_number": 1,
            "status": "COMPLETED",
        })
        self.opp_id = self.repo.insert_opportunity({
            "id": "disc_0001",
            "title": "Staff PM",
            "company": "Swiggy",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
            "current_application_status": "NOT_APPLIED",
        })

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("review_server.db_repo")
    def test_gmail_status_endpoint_reports_dynamic_redirect_uri(self, mock_repo):
        mock_repo.get_or_create_email_sync_checkpoint.return_value = None
        mock_repo.list_career_events.return_value = []

        # Test on port 8080
        handler_8080 = MockHTTPHandler(b"", method="GET", path="/api/gmail/status", port=8080)
        handler_8080.do_GET()
        data_8080 = json.loads(handler_8080.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data_8080["server_port"], 8080)
        self.assertEqual(data_8080["redirect_uri"], "http://localhost:8080/api/gmail/callback")

        # Test on port 8081
        handler_8081 = MockHTTPHandler(b"", method="GET", path="/api/gmail/status", port=8081)
        handler_8081.do_GET()
        data_8081 = json.loads(handler_8081.wfile.getvalue().decode("utf-8"))
        self.assertEqual(data_8081["server_port"], 8081)
        self.assertEqual(data_8081["redirect_uri"], "http://localhost:8081/api/gmail/callback")

    def test_auth_url_endpoint_configuration_error_without_exposing_secrets(self):
        handler = MockHTTPHandler(b"", method="GET", path="/api/gmail/auth-url", port=8081)
        handler.do_GET()
        data = json.loads(handler.wfile.getvalue().decode("utf-8"))

        self.assertTrue(data.get("is_config_error"))
        self.assertIn("GMAIL_CLIENT_ID", data.get("error", ""))
        self.assertEqual(data.get("redirect_uri"), "http://localhost:8081/api/gmail/callback")
        # Ensure secrets are never exposed
        self.assertNotIn("client_secret", data)
        self.assertNotIn("secret", str(data).lower().replace("gmail_client_secret", ""))

    @patch("review_server.db_repo")
    def test_gmail_sync_dry_run_endpoint(self, mock_repo):
        mock_repo.is_raw_email_processed.return_value = False
        mock_repo.get_opportunity_by_id.return_value = {"id": "disc_0001", "current_application_status": "NOT_APPLIED"}

        req_payload = json.dumps({"dry_run": True, "adapter_type": "mock"}).encode("utf-8")
        handler = MockHTTPHandler(req_payload, method="POST", path="/api/gmail/sync")
        handler.do_POST()

        response_body = handler.wfile.getvalue().decode("utf-8")
        data = json.loads(response_body)
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["dry_run"])
        self.assertIn("formatted_preview", data)
        self.assertIn("CAREER OS — GMAIL SYNC PREVIEW (DRY RUN)", data["formatted_preview"])

    @patch("review_server.db_repo")
    def test_timeline_endpoint(self, mock_repo):
        mock_repo.get_opportunity_timeline.return_value = [
            {"type": "APPLICATION_CONFIRMATION", "subject": "Thanks for applying", "timestamp": "2026-08-31T10:00:00Z"}
        ]

        handler = MockHTTPHandler(b"", method="GET", path="/api/timeline?opportunity_id=disc_0001")
        handler.do_GET()

        response_body = handler.wfile.getvalue().decode("utf-8")
        data = json.loads(response_body)
        self.assertEqual(data["opportunity_id"], "disc_0001")
        self.assertEqual(len(data["timeline"]), 1)


if __name__ == "__main__":
    unittest.main()
