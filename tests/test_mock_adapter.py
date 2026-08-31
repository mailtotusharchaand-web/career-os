"""
tests.test_mock_adapter — Unit tests for deterministic MockEmailAdapter and standard fixtures.
"""

import unittest
from career_os.email.adapters.mock_adapter import MockEmailAdapter
from career_os.email.classifier import EmailClassifier
from career_os.email.models import EventType


class TestMockAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = MockEmailAdapter()
        self.classifier = EmailClassifier()

    def test_mock_adapter_connection_and_fetching(self):
        self.assertTrue(self.adapter.is_connected())
        self.assertEqual(self.adapter.get_account_email(), "candidate.tushar@example.com")

        messages = self.adapter.fetch_messages(max_results=10)
        self.assertEqual(len(messages), 8)

        # Test disconnect behavior
        self.adapter.set_connected(False)
        self.assertFalse(self.adapter.is_connected())
        self.assertIsNone(self.adapter.get_account_email())
        with self.assertRaises(ConnectionError):
            self.adapter.fetch_messages()

    def test_mock_fixtures_classifications(self):
        fixtures = self.adapter.get_standard_mock_fixtures()
        events = [self.classifier.classify(m).event_type for m in fixtures]

        # Verify exact coverage across all synthetic categories
        self.assertIn(EventType.APPLICATION_CONFIRMATION, events)
        self.assertIn(EventType.INTERVIEW_INVITATION, events)
        self.assertIn(EventType.ASSESSMENT_REQUEST, events)
        self.assertIn(EventType.REJECTION, events)
        self.assertIn(EventType.OFFER, events)
        self.assertIn(EventType.RECRUITER_CONTACT, events)
        self.assertIn(EventType.IRRELEVANT, events)


if __name__ == "__main__":
    unittest.main()
