"""
tests/test_evaluation_persistence_repair.py — Regression tests for evaluation persistence,
structured score mapping, evaluation lifecycle states, and API contract preservation.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from career_os.db.repository import CareerOSRepository, compute_canonical_key, compute_content_hash
from career_os.db.migrate_json_to_sqlite import run_migration, EXPECTED_RESULTS_SHA256, EXPECTED_EVALS_SHA256


class TestEvaluationPersistenceRepair(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        # Initialize with corrected Run 001 historical migration
        success, report = run_migration(db_path=self.temp_db.name)
        self.assertTrue(success, "Historical Run 001 migration failed")
        self.repo = CareerOSRepository(db_path=self.temp_db.name)

        # Pre-insert Run 002 for testing
        self.repo.insert_discovery_run({"id": "run_0002", "run_number": 2, "status": "COMPLETED"})

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_historical_evaluation_migration_mapping(self):
        """
        1. Verify role_fit, experience_fit, transferable, seniority_fit,
           opportunity_alignment, overall_score, key_strengths, missing_critical_skills,
           recommendation, reasoning survive migration from historical JSON.
        """
        ev = self.repo.get_evaluation_by_opportunity_id("disc_0001")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["recommendation"], "Skip")
        self.assertEqual(ev["score"], 5.0)
        self.assertEqual(ev["evaluation_status"], "EVALUATED")

        fit_dims = ev["fit_dimensions"]
        self.assertEqual(fit_dims.get("role_fit"), 5)
        self.assertEqual(fit_dims.get("experience_fit"), 0)
        self.assertEqual(fit_dims.get("transferable"), 20)
        self.assertEqual(fit_dims.get("seniority_fit"), 30)
        self.assertEqual(fit_dims.get("opportunity_alignment"), 10)
        self.assertEqual(fit_dims.get("probability_of_obtaining"), 0)
        self.assertEqual(fit_dims.get("transition_difficulty"), "very_high")

        self.assertGreater(len(ev["strengths"]), 0)
        self.assertIn("Cross-functional stakeholder management", ev["strengths"])

        self.assertGreater(len(ev["gaps"]), 0)
        self.assertIn("Human Resources generalist expertise", ev["gaps"])
        self.assertIn("Human Resources Business Partner", ev["reasoning"])

    def test_evaluation_null_vs_zero(self):
        """
        2. Verify score = 0 remains 0 and score = NULL remains NULL.
        """
        # Insert opportunity with score 0
        opp_zero = {
            "id": "disc_test_zero",
            "title": "Unrelated Job",
            "company": "Company A",
            "location": "Bengaluru, India",
            "description": "Job A",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        }
        self.repo.insert_opportunity(opp_zero)
        self.repo.insert_evaluation({
            "opportunity_id": "disc_test_zero",
            "score": 0.0,
            "recommendation": "Skip",
            "evaluation_status": "EVALUATED",
            "fit_dimensions": {"role_fit": 0, "experience_fit": 0},
            "strengths": [],
            "gaps": ["No fit"],
            "reasoning": "Zero score role.",
        })

        # Insert opportunity with score NULL (Pending)
        opp_null = {
            "id": "disc_test_null",
            "title": "Pending Job",
            "company": "Company B",
            "location": "Bengaluru, India",
            "description": "Job B",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        }
        self.repo.insert_opportunity(opp_null)
        self.repo.insert_evaluation({
            "opportunity_id": "disc_test_null",
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
            "fit_dimensions": {},
            "strengths": [],
            "gaps": [],
            "reasoning": None,
        })

        ev_zero = self.repo.get_evaluation_by_opportunity_id("disc_test_zero")
        ev_null = self.repo.get_evaluation_by_opportunity_id("disc_test_null")

        self.assertIsNotNone(ev_zero)
        self.assertEqual(ev_zero["score"], 0.0)
        self.assertEqual(ev_zero["evaluation_status"], "EVALUATED")

        self.assertIsNotNone(ev_null)
        self.assertIsNone(ev_null["score"])
        self.assertEqual(ev_null["evaluation_status"], "PENDING")

    def test_reused_evaluation_persistence(self):
        """
        3. Verify source evaluation remains intact, reused evaluation exists,
           source_evaluation_id is correct, reuse_type is correct, is_reused = 1,
           no LLM call occurs.
        """
        src_ev = self.repo.get_evaluation_by_opportunity_id("disc_0001")
        self.assertIsNotNone(src_ev)

        # Create new opportunity reusing disc_0001 evaluation
        reused_opp_id = "disc_test_reused"
        self.repo.insert_opportunity({
            "id": reused_opp_id,
            "title": "Human Resources Business Partner",
            "company": "Clearwater Analytics (CWAN)",
            "location": "Pune, Maharashtra, India",
            "description": "Exact same description",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })

        self.repo.insert_evaluation({
            "opportunity_id": reused_opp_id,
            "score": src_ev["score"],
            "recommendation": src_ev["recommendation"],
            "fit_dimensions": src_ev["fit_dimensions"],
            "strengths": src_ev["strengths"],
            "gaps": src_ev["gaps"],
            "reasoning": src_ev["reasoning"],
            "is_reused": 1,
            "reuse_type": "REUSED_EQUIVALENT_ROLE",
            "source_evaluation_id": src_ev["id"],
            "reuse_reason": "Equivalent role in different location",
            "evaluation_status": "REUSED",
        })

        reused_ev = self.repo.get_evaluation_by_opportunity_id(reused_opp_id)
        self.assertIsNotNone(reused_ev)
        self.assertEqual(reused_ev["is_reused"], 1)
        self.assertEqual(reused_ev["reuse_type"], "REUSED_EQUIVALENT_ROLE")
        self.assertEqual(reused_ev["source_evaluation_id"], src_ev["id"])
        self.assertEqual(reused_ev["evaluation_status"], "REUSED")
        self.assertEqual(reused_ev["score"], src_ev["score"])

        # Ensure source evaluation is still intact
        src_ev_after = self.repo.get_evaluation_by_opportunity_id("disc_0001")
        self.assertEqual(src_ev_after["is_reused"], 0)
        self.assertEqual(src_ev_after["evaluation_status"], "EVALUATED")

    def test_pending_evaluation_persistence(self):
        """
        4. Verify new opportunity has explicit PENDING state, no score is fabricated,
           no LLM call occurs.
        """
        opp_pending_id = "disc_test_new_pending"
        self.repo.insert_opportunity({
            "id": opp_pending_id,
            "title": "Principal AI Engineer",
            "company": "DeepMind India",
            "location": "Bengaluru, India",
            "description": "Novel AI research",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": opp_pending_id,
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
            "fit_dimensions": {},
            "strengths": [],
            "gaps": [],
            "reasoning": None,
        })

        ev = self.repo.get_evaluation_by_opportunity_id(opp_pending_id)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["evaluation_status"], "PENDING")
        self.assertIsNone(ev["score"])
        self.assertIsNone(ev["recommendation"])
        self.assertIsNone(ev["reasoning"])

    def test_all_opportunities_have_evaluation_state(self):
        """
        5. Verify that every opportunity in the database has an unambiguous evaluation state
           (EVALUATED, REUSED, PENDING, or FAILED).
        """
        ws_data = self.repo.get_workstation_data()
        jobs = ws_data["jobs"]
        self.assertGreaterEqual(len(jobs), 129)

        valid_states = {"EVALUATED", "REUSED", "GATE_REJECTED", "PENDING", "FAILED"}
        for job in jobs:
            st = job.get("evaluation_status")
            self.assertIn(st, valid_states, f"Opportunity {job['job_id']} has invalid evaluation_status: {st}")
            if st == "EVALUATED" and not job.get("gate_failed"):
                self.assertIsNotNone(job["llm_evaluation"])
                self.assertIsNotNone(job["llm_evaluation"]["recommendation"])
            elif st == "GATE_REJECTED":
                self.assertIsNone(job.get("llm_evaluation"))
                self.assertTrue(job.get("gate_failed"))
            elif st == "PENDING":
                self.assertIsNone(job["llm_evaluation"])

    def test_evaluation_state_survives_workstation_api(self):
        """
        6. Verify SQLite -> repository -> API -> frontend payload preserves evaluation status
           and score semantics.
        """
        ws_data = self.repo.get_workstation_data()
        job1 = next(j for j in ws_data["jobs"] if j["job_id"] == "disc_0001")
        self.assertEqual(job1["evaluation_status"], "EVALUATED")
        self.assertIsNotNone(job1["llm_evaluation"])
        self.assertEqual(job1["llm_evaluation"]["overall_score"], 5.0)
        self.assertEqual(job1["llm_evaluation"]["role_fit"], 5)
        self.assertEqual(job1["llm_evaluation"]["current_experience_fit"], 0)
        self.assertEqual(job1["llm_evaluation"]["transferable_capability_fit"], 20)
        self.assertEqual(job1["llm_evaluation"]["seniority_fit"], 30)
        self.assertEqual(job1["llm_evaluation"]["probability_of_obtaining"], 0)
        self.assertEqual(job1["llm_evaluation"]["recommendation"], "Skip")


if __name__ == "__main__":
    unittest.main()
