"""
tests.test_gmail_adapter — Unit tests for GmailEmailAdapter payload parsing and query generation.
"""

import unittest
import base64
import tempfile
import shutil
from career_os.email.adapters.gmail_adapter import GmailEmailAdapter, _decode_base64url, _extract_body_text_from_payload
from career_os.email.token_store import LocalSecureFileTokenStore


class TestGmailAdapter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.token_store = LocalSecureFileTokenStore(base_dir=self.temp_dir)
        self.adapter = GmailEmailAdapter(
            account_email="candidate.test@gmail.com",
            token_store=self.token_store,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_builder_includes_ats_and_keywords(self):
        q = self.adapter.build_search_query()
        self.assertIn("application", q)
        self.assertIn("interview", q)
        self.assertIn("greenhouse.io", q)
        self.assertIn("lever.co", q)

        q_date = self.adapter.build_search_query(after_date="2026-08-01")
        self.assertIn("after:2026/08/01", q_date)

    def test_parse_gmail_message_payload(self):
        body_content = "Hi Tushar,\n\nThank you for applying to Razorpay for the Principal PM Payments position."
        encoded_body = base64.urlsafe_b64encode(body_content.encode("utf-8")).decode("ascii")

        raw_gmail_json = {
            "id": "18f9293847291a82",
            "threadId": "18f9293847291a82",
            "labelIds": ["INBOX", "UNREAD"],
            "snippet": "Thank you for applying to Razorpay for the Principal PM...",
            "internalDate": "1788166800000",  # timestamp in ms
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Thank you for applying - Razorpay"},
                    {"name": "From", "value": "Razorpay Talent <jobs@razorpay.com>"},
                    {"name": "To", "value": "candidate.test@gmail.com"},
                    {"name": "Date", "value": "Mon, 31 Aug 2026 10:00:00 +0000"},
                ],
                "body": {
                    "data": encoded_body,
                    "size": len(body_content),
                },
            },
        }

        parsed = self.adapter.parse_gmail_message(raw_gmail_json)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.provider, "gmail")
        self.assertEqual(parsed.message_id, "18f9293847291a82")
        self.assertEqual(parsed.thread_id, "18f9293847291a82")
        self.assertEqual(parsed.subject, "Thank you for applying - Razorpay")
        self.assertEqual(parsed.sender_email, "jobs@razorpay.com")
        self.assertEqual(parsed.sender_domain, "razorpay.com")
        self.assertIn("Principal PM Payments", parsed.body_text)


if __name__ == "__main__":
    unittest.main()
