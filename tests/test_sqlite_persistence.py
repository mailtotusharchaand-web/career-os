"""
tests/test_sqlite_persistence.py — Unit & Integration tests for SQLite Persistent Memory Layer.
"""

import json
import os
import tempfile
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.db.repository import CareerOSRepository, compute_canonical_key, compute_content_hash
from career_os.db.migrate_json_to_sqlite import run_migration


class TestSQLitePersistence(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.repo = CareerOSRepository(db_path=self.temp_db.name)
        self.repo.init_db()

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_schema_tables_created(self):
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r["name"] for r in cur.fetchall()]

        expected_tables = [
            "discovery_runs",
            "opportunities",
            "opportunity_sources",
            "discovery_run_opportunities",
            "evaluations",
            "human_reviews",
            "application_status_history",
            "evaluation_profiles",
        ]
        for t in expected_tables:
            self.assertIn(t, tables)

    def test_opportunity_identity_distinct_locations(self):
        """Verify that same title + company in different cities produce separate opportunity records."""
        key1 = compute_canonical_key("Senior PM", "Company A", "Bengaluru, Karnataka, India")
        key2 = compute_canonical_key("Senior PM", "Company A", "Gurugram, Haryana, India")
        self.assertNotEqual(key1, key2)

        opp1 = {
            "id": "opp_blr",
            "canonical_key": key1,
            "title": "Senior PM",
            "company": "Company A",
            "location": "Bengaluru, Karnataka, India",
            "description": "Leading payments infrastructure.",
        }
        opp2 = {
            "id": "opp_ggn",
            "canonical_key": key2,
            "title": "Senior PM",
            "company": "Company A",
            "location": "Gurugram, Haryana, India",
            "description": "Leading payments infrastructure.",
        }

        # First insert dummy run
        self.repo.insert_discovery_run({"id": "run_test", "run_number": 10})

        self.repo.insert_opportunity({**opp1, "first_seen_run_id": "run_test", "last_seen_run_id": "run_test"})
        self.repo.insert_opportunity({**opp2, "first_seen_run_id": "run_test", "last_seen_run_id": "run_test"})

        res1 = self.repo.get_opportunity_by_id("opp_blr")
        res2 = self.repo.get_opportunity_by_id("opp_ggn")
        self.assertIsNotNone(res1)
        self.assertIsNotNone(res2)
        self.assertEqual(res1["location"], "Bengaluru, Karnataka, India")
        self.assertEqual(res2["location"], "Gurugram, Haryana, India")

    def test_evaluation_reuse_hierarchy(self):
        """Test Level 1, Level 2, Level 3 reuse rules and Level 4/5 fallback."""
        self.repo.insert_discovery_run({"id": "run_test", "run_number": 1})

        # Insert Opportunity 1
        opp1 = {
            "id": "disc_001",
            "title": "Staff PM",
            "company": "Razorpay",
            "location": "Bengaluru, India",
            "description": "Merchant payouts engine architecture and rails.",
        }
        self.repo.insert_opportunity({**opp1, "first_seen_run_id": "run_test", "last_seen_run_id": "run_test"})

        # Insert Evaluation for Opportunity 1
        eval1 = {
            "id": "eval_disc_001",
            "opportunity_id": "disc_001",
            "recommendation": "YES",
            "score": 9.2,
            "reasoning": "Strong match for candidate fintech & payment rails background.",
            "description": opp1["description"],
        }
        self.repo.insert_evaluation(eval1)

        # Level 1: Exact opportunity ID match
        reused_eval, reuse_type, reason = self.repo.find_reusable_evaluation({"id": "disc_001"})
        self.assertEqual(reuse_type, "REUSED_EXACT")
        self.assertEqual(reused_eval["score"], 9.2)

        # Level 2: Same posting description hash (different ID e.g. from another source)
        diff_id_same_desc = {
            "id": "disc_999",
            "title": "Staff PM",
            "company": "Razorpay",
            "location": "Bengaluru, India",
            "description": "Merchant payouts engine architecture and rails.",
        }
        reused_eval2, reuse_type2, reason2 = self.repo.find_reusable_evaluation(diff_id_same_desc)
        self.assertIn(reuse_type2, ("REUSED_EXACT", "REUSED_SAME_POSTING"))

        # Level 3: Same company + exact role content equivalent in different city
        same_comp_diff_city = {
            "id": "disc_pune",
            "title": "Staff PM",
            "company": "Razorpay",
            "location": "Pune, Maharashtra, India",
            "description": "Merchant payouts engine architecture and rails.",
        }
        reused_eval3, reuse_type3, reason3 = self.repo.find_reusable_evaluation(same_comp_diff_city)
        self.assertIn(reuse_type3, ("REUSED_SAME_POSTING", "REUSED_EQUIVALENT_ROLE"))

        # Level 4/5: Different company -> must NOT reuse evaluation
        diff_comp = {
            "id": "disc_diff_comp",
            "title": "Staff PM",
            "company": "Competitor X",
            "location": "Bengaluru, India",
            "description": "Enterprise healthcare scheduling platform.",
        }
        reused_eval4 = self.repo.find_reusable_evaluation(diff_comp)
        self.assertIsNone(reused_eval4)

    def test_application_status_persistence_across_rediscovery(self):
        """Verify that an APPLIED opportunity retains APPLIED status when rediscovered."""
        self.repo.insert_discovery_run({"id": "run_0001", "run_number": 1})
        self.repo.insert_discovery_run({"id": "run_0002", "run_number": 2})

        opp = {
            "id": "disc_applied_test",
            "title": "Director of Product",
            "company": "Flipkart",
            "location": "Bengaluru, India",
            "description": "Leading supply chain product division.",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
        }
        self.repo.insert_opportunity(opp)

        # Human applies to the job
        self.repo.save_human_review({
            "opportunity_id": "disc_applied_test",
            "verdict": "RELEVANT",
            "counterfactual": "YES",
            "priority": "HIGH",
            "opportunity_status": "AVAILABLE",
            "application_status": "APPLIED",
            "notes": "Applied via referral on Aug 20",
        })

        # Run 002 rediscovers the opportunity
        self.repo.mark_opportunity_seen("disc_applied_test", run_id="run_0002")

        # Opportunity must remain APPLIED in DB and not reset to NOT_APPLIED
        loaded = self.repo.get_opportunity_by_id("disc_applied_test")
        self.assertEqual(loaded["current_application_status"], "APPLIED")
        self.assertEqual(loaded["appearance_count"], 2)
        self.assertEqual(loaded["last_seen_run_id"], "run_0002")

        # Verify application status history audit log
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT * FROM application_status_history WHERE opportunity_id = 'disc_applied_test';")
            history = [dict(r) for r in cur.fetchall()]
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["previous_status"], "NOT_APPLIED")
            self.assertEqual(history[0]["new_status"], "APPLIED")


class TestHistoricalMigration(unittest.TestCase):

    def test_run_migration_parity(self):
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        try:
            success, report = run_migration(db_path=temp_db.name)
            self.assertTrue(success)
            self.assertEqual(report["unmatched_opportunities"], 0)
            self.assertEqual(report["unmatched_evaluations"], 0)
            self.assertEqual(report["unmatched_reviews"], 0)
            self.assertTrue(report["results_json_sha256_verified"])
            self.assertTrue(report["evals_json_sha256_verified"])
        finally:
            if os.path.exists(temp_db.name):
                try:
                    os.remove(temp_db.name)
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
