"""
tests.test_email_models — Unit tests for email models and dataclass serialization.
"""

import unittest
from datetime import datetime, timezone
from career_os.email.models import (
    RawEmailMessage,
    EmailClassification,
    OpportunityMatchResult,
    CareerEvent,
    EventType,
    ConfidenceLevel,
    EventStatus,
)


class TestEmailModels(unittest.TestCase):
    def test_raw_email_message_creation_and_properties(self):
        msg = RawEmailMessage(
            provider="gmail",
            account_id="test@example.com",
            message_id="msg_12345",
            thread_id="th_12345",
            sender="Recruiting Team <jobs@company.com>",
            recipients=["test@example.com"],
            subject="Interview Invitation",
            body_text="Hi Tushar,\n\nWe would like to invite you for an interview.\n\nBest,\nCompany",
            received_at="2026-08-31T10:00:00Z",
        )
        self.assertEqual(msg.sender_email, "jobs@company.com")
        self.assertEqual(msg.sender_domain, "company.com")
        self.assertTrue(len(msg.body_hash) == 64)
        self.assertTrue(len(msg.snippet) > 0)
        self.assertIn("interview", msg.snippet.lower())

        # Test dictionary serialization & round-trip
        data = msg.to_dict()
        self.assertEqual(data["message_id"], "msg_12345")
        roundtrip = RawEmailMessage.from_dict(data)
        self.assertEqual(roundtrip.message_id, msg.message_id)
        self.assertEqual(roundtrip.sender_email, "jobs@company.com")

    def test_career_event_serialization(self):
        event = CareerEvent(
            id="event_001",
            event_type=EventType.APPLICATION_CONFIRMATION,
            opportunity_id="disc_0001",
            occurred_at="2026-08-31T10:00:00Z",
            source_provider="mock",
            source_account_id="test@example.com",
            source_message_id="mock_msg_001",
            source_thread_id="mock_th_001",
            confidence_score=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            status=EventStatus.AUTOMATIC_APPLIED,
            evidence={"subject": "Thank you for applying", "company": "Swiggy"},
            candidate_matches=[],
        )
        d = event.to_dict()
        self.assertEqual(d["event_type"], "APPLICATION_CONFIRMATION")
        self.assertEqual(d["confidence_level"], "HIGH")
        self.assertEqual(d["status"], "AUTOMATIC_APPLIED")

        roundtrip = CareerEvent.from_dict(d)
        self.assertEqual(roundtrip.id, "event_001")
        self.assertEqual(roundtrip.event_type, EventType.APPLICATION_CONFIRMATION)
        self.assertEqual(roundtrip.status, EventStatus.AUTOMATIC_APPLIED)


if __name__ == "__main__":
    unittest.main()
