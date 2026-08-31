"""
tests.test_email_persistence — Integration tests for SQLite persistence, idempotency,
atomic transactions, restart recovery, and auditable history invariants.
"""

import unittest
import tempfile
import os
import shutil
from pathlib import Path
from career_os.db.repository import CareerOSRepository


class TestEmailPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_career_os.db")
        self.repo = CareerOSRepository(db_path=self.db_path)
        self.repo.init_db()

        # Seed discovery run and opportunity
        self.run_id = self.repo.insert_discovery_run({
            "id": "run_0001",
            "run_number": 1,
            "status": "COMPLETED",
        })
        self.opp_id = self.repo.insert_opportunity({
            "id": "disc_0001",
            "title": "Principal Product Manager",
            "company": "Swiggy",
            "location": "Bengaluru, India",
            "description": "Lead core search & discovery.",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
            "current_application_status": "NOT_APPLIED",
        })

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_career_event_and_transition_atomic(self):
        event_data = {
            "id": "evt_test_001",
            "event_type": "APPLICATION_CONFIRMATION",
            "opportunity_id": self.opp_id,
            "occurred_at": "2026-08-31T10:00:00Z",
            "source_provider": "mock",
            "source_account_id": "candidate@example.com",
            "source_message_id": "msg_001",
            "source_thread_id": "th_001",
            "confidence_score": 0.95,
            "confidence_level": "HIGH",
            "status": "AUTOMATIC_APPLIED",
            "evidence": {"subject": "Application Received", "company": "Swiggy"},
            "candidate_matches": [],
            "notes": "Legal forward transition: NOT_APPLIED -> APPLIED",
        }
        raw_msg = {
            "provider": "mock",
            "account_id": "candidate@example.com",
            "message_id": "msg_001",
            "thread_id": "th_001",
            "sender": "Swiggy <jobs@swiggy.in>",
            "sender_domain": "swiggy.in",
            "recipients": ["candidate@example.com"],
            "subject": "Application Received",
            "snippet": "We have received your application...",
            "body_hash": "dummyhash123",
            "received_at": "2026-08-31T10:00:00Z",
            "labels": ["INBOX"],
        }

        eid, did_mutate = self.repo.record_career_event_and_transition(
            event_data=event_data,
            raw_message_data=raw_msg,
            should_mutate_status=True,
            new_application_status="APPLIED",
            transition_notes="Application confirmed via email",
        )

        self.assertEqual(eid, "evt_test_001")
        self.assertTrue(did_mutate)

        # Verify opportunity status updated
        opp = self.repo.get_opportunity_by_id(self.opp_id)
        self.assertEqual(opp["current_application_status"], "APPLIED")

        # Verify career event persisted
        ev = self.repo.get_career_event("evt_test_001")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["event_type"], "APPLICATION_CONFIRMATION")

        # Verify application status history logged with audit chain
        timeline = self.repo.get_opportunity_timeline(self.opp_id)
        status_changes = [t for t in timeline if t["type"] == "STATUS_CHANGE"]
        self.assertEqual(len(status_changes), 1)
        self.assertEqual(status_changes[0]["previous_status"], "NOT_APPLIED")
        self.assertEqual(status_changes[0]["new_status"], "APPLIED")
        self.assertIn("evt_test_001", status_changes[0]["notes"])

    def test_idempotency_duplicate_message_no_duplicate_event_or_transition(self):
        event_data = {
            "id": "evt_test_002",
            "event_type": "APPLICATION_CONFIRMATION",
            "opportunity_id": self.opp_id,
            "occurred_at": "2026-08-31T10:00:00Z",
            "source_provider": "mock",
            "source_account_id": "candidate@example.com",
            "source_message_id": "msg_002",
            "source_thread_id": "th_002",
            "confidence_score": 0.95,
            "confidence_level": "HIGH",
            "status": "AUTOMATIC_APPLIED",
            "evidence": {"subject": "Application Received"},
            "candidate_matches": [],
            "notes": "First sync",
        }
        raw_msg = {
            "provider": "mock",
            "account_id": "candidate@example.com",
            "message_id": "msg_002",
            "body_hash": "hash002",
        }

        # First recording
        self.repo.record_career_event_and_transition(
            event_data=event_data,
            raw_message_data=raw_msg,
            should_mutate_status=True,
            new_application_status="APPLIED",
            transition_notes="First pass",
        )

        # Check is_raw_email_processed
        self.assertTrue(self.repo.is_raw_email_processed("mock", "candidate@example.com", "msg_002"))

        # Second recording (Duplicate sync attempt)
        self.repo.record_career_event_and_transition(
            event_data=event_data,
            raw_message_data=raw_msg,
            should_mutate_status=True,
            new_application_status="APPLIED",
            transition_notes="Duplicate pass",
        )

        # Verify only 1 career event exists
        events = self.repo.list_career_events(opportunity_id=self.opp_id)
        self.assertEqual(len(events), 1)

        # Verify only 1 status change exists
        timeline = self.repo.get_opportunity_timeline(self.opp_id)
        status_changes = [t for t in timeline if t["type"] == "STATUS_CHANGE"]
        self.assertEqual(len(status_changes), 1)

    def test_checkpoint_persistence_and_restart_recovery(self):
        self.repo.get_or_create_email_sync_checkpoint("mock", "candidate@example.com")
        self.repo.update_email_sync_checkpoint(
            provider="mock",
            account_id="candidate@example.com",
            last_synced_at="2026-08-31T12:00:00Z",
            last_message_timestamp="2026-08-31T11:59:00Z",
            sync_status="HEALTHY",
            messages_increment=5,
        )

        # Simulate app restart with new repository instance pointing to same file
        restarted_repo = CareerOSRepository(db_path=self.db_path)
        cp = restarted_repo.get_or_create_email_sync_checkpoint("mock", "candidate@example.com")
        self.assertEqual(cp["messages_processed"], 5)
        self.assertEqual(cp["last_synced_at"], "2026-08-31T12:00:00Z")
        self.assertEqual(cp["sync_status"], "HEALTHY")

    def test_transaction_atomic_rollback_on_failure(self):
        # Trigger failure by attempting to update non-existent constraint or invalid query in transactional block
        initial_events = len(self.repo.list_career_events())

        with self.assertRaises(Exception):
            with self.repo.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO career_events (
                        id, event_type, occurred_at, source_provider, source_account_id,
                        source_message_id, confidence_score, confidence_level, status, evidence_json,
                        created_at, updated_at
                    ) VALUES ('evt_fail', 'APPLICATION_CONFIRMATION', '2026-08-31T10:00:00Z', 'mock', 'u@e.com', 'm_fail', 0.9, 'HIGH', 'AUTOMATIC_APPLIED', '{}', 'now', 'now');
                    """
                )
                # Intentionally cause a foreign key / SQL syntax failure inside the same transaction
                conn.execute("INSERT INTO non_existent_table_for_rollback_test VALUES (1);")

        # Verify atomic rollback: no partial event remained
        reloaded_events = len(self.repo.list_career_events())
        self.assertEqual(reloaded_events, initial_events)

    def test_thread_continuity_timeline(self):
        # 1. First event: Application confirmation
        self.repo.record_career_event_and_transition(
            event_data={
                "id": "evt_thread_1",
                "event_type": "APPLICATION_CONFIRMATION",
                "opportunity_id": self.opp_id,
                "occurred_at": "2026-08-31T10:00:00Z",
                "source_provider": "mock",
                "source_account_id": "candidate@example.com",
                "source_message_id": "msg_th_1",
                "source_thread_id": "thread_abc",
                "confidence_score": 0.95,
                "confidence_level": "HIGH",
                "status": "AUTOMATIC_APPLIED",
                "evidence": {"subject": "Application Received"},
            },
            should_mutate_status=True,
            new_application_status="APPLIED",
        )

        # 2. Second event: Interview invitation in same thread
        self.repo.record_career_event_and_transition(
            event_data={
                "id": "evt_thread_2",
                "event_type": "INTERVIEW_INVITATION",
                "opportunity_id": self.opp_id,
                "occurred_at": "2026-08-31T12:00:00Z",
                "source_provider": "mock",
                "source_account_id": "candidate@example.com",
                "source_message_id": "msg_th_2",
                "source_thread_id": "thread_abc",
                "confidence_score": 0.95,
                "confidence_level": "HIGH",
                "status": "AUTOMATIC_APPLIED",
                "evidence": {"subject": "Interview Scheduled"},
            },
            should_mutate_status=True,
            new_application_status="INTERVIEW",
        )

        # 3. Verify final state and timeline progression
        opp = self.repo.get_opportunity_by_id(self.opp_id)
        self.assertEqual(opp["current_application_status"], "INTERVIEW")

        timeline = self.repo.get_opportunity_timeline(self.opp_id)
        self.assertEqual(len(timeline), 4)  # 2 STATUS_CHANGE + 2 CAREER_EVENT
        status_transitions = [(t["previous_status"], t["new_status"]) for t in timeline if t["type"] == "STATUS_CHANGE"]
        self.assertEqual(status_transitions, [("NOT_APPLIED", "APPLIED"), ("APPLIED", "INTERVIEW")])


if __name__ == "__main__":
    unittest.main()
