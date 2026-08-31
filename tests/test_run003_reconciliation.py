"""
tests.test_run003_reconciliation — Comprehensive tests for gate repair, longitudinal Run 003 discovery, evaluation completeness, and human review protection.
"""

import unittest
import tempfile
import shutil
import os
import json
from unittest.mock import patch, MagicMock

from career_os.db.repository import CareerOSRepository, compute_canonical_key
from career_os.discovery.evaluator_runner import EvaluationRunner
from evaluate import _gate_employment_type, run_explicit_constraint_gates


class TestRun003Reconciliation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_reconciliation.db")
        self.repo = CareerOSRepository(db_path=self.db_path)
        self.repo.init_db()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Gate Repair & Word-Boundary Tests
    def test_gate_word_boundary_rules(self):
        # Must NOT be rejected
        self.assertTrue(_gate_employment_type({"title": "Product Manager, International Emerging Stores"})[0])
        self.assertTrue(_gate_employment_type({"title": "Internal Audit Manager — Payments"})[0])
        self.assertTrue(_gate_employment_type({"title": "Internet Security Product Lead"})[0])
        self.assertTrue(_gate_employment_type({"title": "Lead PM — Interoperability"})[0])
        self.assertTrue(_gate_employment_type({"title": "Staff Engineer, Internally Facing Systems"})[0])

        # MUST be rejected
        self.assertFalse(_gate_employment_type({"title": "Software Engineering Intern"})[0])
        self.assertFalse(_gate_employment_type({"title": "Product Management Internship"})[0])
        self.assertFalse(_gate_employment_type({"title": "Intern-Firmware Developer"})[0])
        self.assertFalse(_gate_employment_type({"title": "Lead Product Manager", "job_type": "internship"})[0])
        self.assertFalse(_gate_employment_type({"title": "Operations Consultant", "job_type": "part-time"})[0])

    # 2. Evaluation State Semantics (Gate Rejected != Pending)
    def test_gate_rejected_state_semantics_in_workstation_data(self):
        run_id = self.repo.insert_discovery_run({"id": "run_0001", "run_number": 1})
        opp_id = self.repo.insert_opportunity({
            "id": "disc_test_01",
            "title": "Intern-Firmware Developer",
            "company": "Hardware Labs",
            "location": "Bengaluru, India",
            "first_seen_run_id": run_id,
        })
        self.repo.insert_evaluation({
            "opportunity_id": opp_id,
            "gate_failed": 1,
            "gate_failure_reasons": ["employment_type: excluded keyword in title: 'intern'"],
            "evaluation_status": "GATE_REJECTED",
        })

        ws_data = self.repo.get_workstation_data()
        job = ws_data["jobs"][0]

        # Invariants
        self.assertEqual(job["evaluation_status"], "GATE_REJECTED")
        self.assertTrue(job["gate_failed"])
        self.assertIsNone(job["llm_evaluation"])
        self.assertIn("employment_type: excluded keyword in title: 'intern'", job["gate_failure_reasons"])

    # 3. Longitudinal Discovery Independence & Human Review Protection
    def test_longitudinal_discovery_and_review_safety(self):
        # Run 001
        r1_id = self.repo.insert_discovery_run({"id": "run_0001", "run_number": 1})
        opp1 = self.repo.insert_opportunity({
            "id": "disc_0001",
            "title": "Fintech PM",
            "company": "Razorpay",
            "location": "Bengaluru, India",
            "first_seen_run_id": r1_id,
        })
        self.repo.insert_evaluation({
            "opportunity_id": opp1,
            "score": 85.0,
            "recommendation": "Strong Apply",
            "reasoning": "Excellent overlap.",
            "evaluation_status": "EVALUATED",
        })
        # Human review on Run 001
        self.repo.save_human_review({
            "opportunity_id": opp1,
            "verdict": "RELEVANT",
            "counterfactual": "YES",
            "priority": "HIGH",
        })

        # Run 002
        r2_id = self.repo.insert_discovery_run({"id": "run_0002", "run_number": 2})
        opp2 = self.repo.insert_opportunity({
            "id": "disc_0002",
            "title": "Senior PM",
            "company": "Paytm",
            "location": "Noida, India",
            "first_seen_run_id": r2_id,
        })
        self.repo.insert_evaluation({
            "opportunity_id": opp2,
            "score": 75.0,
            "recommendation": "Apply",
            "reasoning": "Solid fit.",
            "evaluation_status": "EVALUATED",
        })

        # Run 003 discovers a new opportunity and recurring opp1
        r3_id = self.repo.insert_discovery_run({"id": "run_0003", "run_number": 3})
        self.repo.mark_opportunity_seen(opp1, run_id=r3_id)
        opp3 = self.repo.insert_opportunity({
            "id": "disc_0003",
            "title": "Lead PM - Emerging Payments",
            "company": "Amazon",
            "location": "Bengaluru, India",
            "first_seen_run_id": r3_id,
        })

        # Verify run 003 opportunity has distinct run ID
        fetched_opp3 = self.repo.get_opportunity_by_id(opp3)
        self.assertEqual(fetched_opp3["first_seen_run_id"], "run_0003")

        # Verify human review on opp1 was completely untouched
        rev = self.repo.get_human_review(opp1)
        self.assertIsNotNone(rev)
        self.assertEqual(rev["verdict"], "RELEVANT")

        # Verify new opp3 is unreviewed
        rev3 = self.repo.get_human_review(opp3)
        self.assertIsNone(rev3)

    # 4. Evaluation Runner Resumability & Corrective Evaluation
    def test_evaluation_runner_corrective_single_opp(self):
        r1_id = self.repo.insert_discovery_run({"id": "run_0001", "run_number": 1})
        opp_id = self.repo.insert_opportunity({
            "id": "disc_0034",
            "title": "Product Manager, International Emerging Stores Payments",
            "company": "Amazon",
            "location": "Bengaluru, India",
            "first_seen_run_id": r1_id,
        })

        mock_llm_response = json.dumps({
            "role_fit": 85,
            "current_experience_fit": 80,
            "transferable_capability_fit": 90,
            "seniority_fit": 85,
            "opportunity_alignment": 90,
            "overall_score": 85,
            "probability_of_obtaining": 70,
            "recommendation": "Strong Apply",
            "reasoning": "Strong match with payments expertise.",
            "key_strengths": ["Enterprise payments", "Amazon background"],
            "missing_critical_skills": ["None critical"],
        })

        runner = EvaluationRunner(
            db_path=self.db_path,
            llm_caller=lambda prompt, cfg: mock_llm_response,
        )

        success = runner.evaluate_single_opportunity_by_id(opp_id)
        self.assertTrue(success)

        ev = self.repo.get_evaluation_by_opportunity_id(opp_id)
        self.assertEqual(ev["evaluation_status"], "EVALUATED")
        self.assertEqual(ev["score"], 85.0)
        self.assertEqual(ev["recommendation"], "Strong Apply")
        self.assertEqual(ev["gate_failed"], 0)


if __name__ == "__main__":
    unittest.main()
