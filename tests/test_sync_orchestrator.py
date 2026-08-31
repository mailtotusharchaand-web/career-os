"""
tests.test_sync_orchestrator — Integration tests for EmailSyncService dry-run mode,
live execution, idempotency, and human confirmation of ambiguous events.
"""

import unittest
import tempfile
import os
import shutil
from career_os.db.repository import CareerOSRepository
from career_os.email.adapters.mock_adapter import MockEmailAdapter
from career_os.email.classifier import EmailClassifier
from career_os.email.matcher import OpportunityMatcher
from career_os.email.sync_service import EmailSyncService


class TestSyncOrchestrator(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_career_os_sync.db")
        self.repo = CareerOSRepository(db_path=self.db_path)
        self.repo.init_db()

        # Seed discovery run
        self.run_id = self.repo.insert_discovery_run({
            "id": "run_0001",
            "run_number": 1,
            "status": "COMPLETED",
        })

        # Seed matching opportunities
        self.swiggy_id = self.repo.insert_opportunity({
            "id": "disc_0001",
            "title": "Product Manager",
            "company": "Swiggy",
            "location": "Bengaluru, Karnataka, India",
            "description": "Drive food delivery product initiatives. Req ID: SWG-9921",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
            "current_application_status": "NOT_APPLIED",
        })

        self.razorpay_id = self.repo.insert_opportunity({
            "id": "disc_0002",
            "title": "Principal PM Payments",
            "company": "Razorpay",
            "location": "Bengaluru, Karnataka, India",
            "description": "Architect next-gen payment gateways.",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
            "current_application_status": "APPLIED",
        })

        self.phonepe_id = self.repo.insert_opportunity({
            "id": "disc_0003",
            "title": "Senior Product Manager",
            "company": "PhonePe",
            "location": "Bengaluru, Karnataka, India",
            "description": "Lead consumer payment features.",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
            "current_application_status": "APPLIED",
        })

        self.zomato_id = self.repo.insert_opportunity({
            "id": "disc_0004",
            "title": "Director of Product",
            "company": "Zomato",
            "location": "Gurugram, India",
            "description": "Core growth leadership.",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
            "current_application_status": "NOT_APPLIED",
        })

        self.adapter = MockEmailAdapter(account_email="candidate.tushar@example.com")
        self.sync_service = EmailSyncService(
            adapter=self.adapter,
            repository=self.repo,
            classifier=EmailClassifier(),
            matcher=OpportunityMatcher(),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dry_run_produces_report_without_modifying_sqlite(self):
        # 1. Execute dry run
        report = self.sync_service.run_sync(dry_run=True)

        self.assertTrue(report.dry_run)
        self.assertEqual(report.total_messages_fetched, 8)
        self.assertTrue(report.new_messages_processed > 0)
        self.assertTrue(len(report.processed_results) > 0)

        # 2. Verify ZERO rows inserted in career_events or email_raw_messages
        with self.repo.connection() as conn:
            ev_count = conn.execute("SELECT count(*) FROM career_events;").fetchone()[0]
            raw_count = conn.execute("SELECT count(*) FROM email_raw_messages;").fetchone()[0]
            hist_count = conn.execute("SELECT count(*) FROM application_status_history;").fetchone()[0]
            cp_count = conn.execute("SELECT count(*) FROM email_sync_checkpoints;").fetchone()[0]

        self.assertEqual(ev_count, 0)
        self.assertEqual(raw_count, 0)
        self.assertEqual(hist_count, 0)
        self.assertEqual(cp_count, 0)

        # 3. Verify opportunity statuses untouched
        swiggy = self.repo.get_opportunity_by_id(self.swiggy_id)
        self.assertEqual(swiggy["current_application_status"], "NOT_APPLIED")

    def test_live_sync_execution_and_amendments(self):
        # 1. Execute live sync
        report = self.sync_service.run_sync(dry_run=False)

        self.assertFalse(report.dry_run)
        self.assertEqual(report.total_messages_fetched, 8)

        # 2. Check Swiggy (Application Confirmation -> APPLIED)
        swiggy = self.repo.get_opportunity_by_id(self.swiggy_id)
        self.assertEqual(swiggy["current_application_status"], "APPLIED")

        # 3. Check Razorpay (Interview Invitation -> INTERVIEW)
        razorpay = self.repo.get_opportunity_by_id(self.razorpay_id)
        self.assertEqual(razorpay["current_application_status"], "INTERVIEW")

        # 4. Check PhonePe (Amendment 2: Assessment Request -> Evidence Only, remains APPLIED)
        phonepe = self.repo.get_opportunity_by_id(self.phonepe_id)
        self.assertEqual(phonepe["current_application_status"], "APPLIED")  # Did not jump to INTERVIEW!

        # 5. Check Zomato (Amendment 3: Recruiter Outreach -> Evidence Only, remains NOT_APPLIED)
        zomato = self.repo.get_opportunity_by_id(self.zomato_id)
        self.assertEqual(zomato["current_application_status"], "NOT_APPLIED")  # Did not jump to APPLIED!

        # 6. Verify Checkpoint advanced
        cp = self.repo.get_or_create_email_sync_checkpoint("mock", "candidate.tushar@example.com")
        self.assertEqual(cp["messages_processed"], 8)
        self.assertEqual(cp["sync_status"], "HEALTHY")

        # 7. Check Invariant: Razorpay has both career_event and application_status_history
        timeline = self.repo.get_opportunity_timeline(self.razorpay_id)
        has_status_change = any(t["type"] == "STATUS_CHANGE" and t["new_status"] == "INTERVIEW" for t in timeline)
        has_event = any(t["type"] == "CAREER_EVENT" and t["event_type"] == "INTERVIEW_INVITATION" for t in timeline)
        self.assertTrue(has_status_change)
        self.assertTrue(has_event)

        # 8. Re-run sync (Idempotency test) -> all messages skipped
        report2 = self.sync_service.run_sync(dry_run=False)
        self.assertEqual(report2.duplicate_messages_skipped, 8)
        self.assertEqual(report2.new_messages_processed, 0)
        self.assertEqual(report2.mutations_applied, 0)

    def test_human_confirmation_of_ambiguous_event(self):
        # Insert a pending event
        event_data = {
            "id": "evt_ambiguous_001",
            "event_type": "INTERVIEW_INVITATION",
            "opportunity_id": None,
            "occurred_at": "2026-08-31T10:00:00Z",
            "source_provider": "mock",
            "source_account_id": "candidate.tushar@example.com",
            "source_message_id": "msg_amb_001",
            "confidence_score": 0.55,
            "confidence_level": "AMBIGUOUS",
            "status": "PENDING_CONFIRMATION",
            "evidence": {"subject": "Interview Invitation"},
            "candidate_matches": [{"opportunity_id": self.swiggy_id, "score": 0.55}],
            "notes": "Ambiguous match",
        }
        self.repo.record_career_event_and_transition(event_data=event_data, should_mutate_status=False)

        # Confirm event for Swiggy
        success = self.repo.confirm_career_event("evt_ambiguous_001", self.swiggy_id, notes="Confirmed by user")
        self.assertTrue(success)

        # Verify Swiggy updated to INTERVIEW
        swiggy = self.repo.get_opportunity_by_id(self.swiggy_id)
        self.assertEqual(swiggy["current_application_status"], "INTERVIEW")

        # Verify event marked CONFIRMED
        ev = self.repo.get_career_event("evt_ambiguous_001")
        self.assertEqual(ev["status"], "CONFIRMED")
        self.assertEqual(ev["opportunity_id"], self.swiggy_id)


if __name__ == "__main__":
    unittest.main()
