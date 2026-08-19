"""
tests/test_pending_evaluation_runner.py — Unit tests for the evaluation runner.
Uses mock LLMs to verify queue isolation, evaluation reuse, validation, resumability, and error handling.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from career_os.db.repository import CareerOSRepository
from career_os.db.migrate_json_to_sqlite import run_migration
from career_os.discovery.evaluator_runner import EvaluationRunner


SAMPLE_MOCK_LLM_RESPONSE = """\
```json
{
  "role_fit": 85,
  "current_experience_fit": 80,
  "transferable_capability_fit": 90,
  "seniority_fit": 85,
  "opportunity_alignment": 80,
  "transition_difficulty": "low",
  "missing_critical_skills": ["Kafka streaming basics"],
  "key_strengths": ["Enterprise Fintech product management", "High volume payments"],
  "career_upside": "high",
  "compensation_upside": "high",
  "probability_of_obtaining": 65,
  "confidence": "high",
  "recommendation": "Apply",
  "reasoning": "Strong match for candidate's fintech background at Amex and Amazon.",
  "evidence": "Candidate has 5+ years building payments workflows.",
  "missing_evidence": "Specific messaging queue architecture.",
  "overall_score": 82
}
```
"""


class TestPendingEvaluationRunner(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        # Initialize with Run 001 historical baseline
        success, report = run_migration(db_path=self.temp_db.name)
        self.assertTrue(success, "Historical Run 001 migration failed")
        self.repo = CareerOSRepository(db_path=self.temp_db.name)
        self.repo.insert_discovery_run({"id": "run_0002", "run_number": 2, "status": "COMPLETED"})

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_pending_queue_selection(self):
        """1. Verify only PENDING opportunities enter the queue."""
        # Insert 1 EVALUATED, 1 PENDING
        self.repo.insert_opportunity({
            "id": "disc_t1_eval",
            "title": "Role Eval",
            "company": "Comp A",
            "location": "Bengaluru, India",
            "description": "Desc A",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t1_eval",
            "score": 75.0,
            "recommendation": "Apply",
            "evaluation_status": "EVALUATED",
        })

        self.repo.insert_opportunity({
            "id": "disc_t2_pend",
            "title": "Role Pend",
            "company": "Comp B",
            "location": "Bengaluru, India",
            "description": "Desc B",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t2_pend",
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
        })

        runner = EvaluationRunner(db_path=self.temp_db.name)
        queue = runner.get_pending_opportunities()
        pending_ids = [q["id"] for q in queue]

        self.assertIn("disc_t2_pend", pending_ids)
        self.assertNotIn("disc_t1_eval", pending_ids)
        self.assertNotIn("disc_0001", pending_ids)  # Run 001 evaluated

    def test_evaluated_not_reprocessed(self):
        """2. Verify EVALUATED opportunities never receive another LLM call."""
        mock_llm = MagicMock(return_value=SAMPLE_MOCK_LLM_RESPONSE)
        runner = EvaluationRunner(db_path=self.temp_db.name, llm_caller=mock_llm)

        # All Run 001 jobs are EVALUATED
        metrics = runner.run()
        self.assertEqual(metrics["pending_at_start"], 0)
        self.assertEqual(metrics["llm_calls_made"], 0)
        mock_llm.assert_not_called()

    def test_reused_not_reprocessed(self):
        """3. Verify REUSED opportunities never receive another LLM call."""
        self.repo.insert_opportunity({
            "id": "disc_t_reused",
            "title": "Reused Role",
            "company": "Comp C",
            "location": "Bengaluru, India",
            "description": "Desc C",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t_reused",
            "score": 60.0,
            "recommendation": "Consider",
            "is_reused": 1,
            "source_evaluation_id": "eval_disc_0001",
            "evaluation_status": "REUSED",
        })

        mock_llm = MagicMock(return_value=SAMPLE_MOCK_LLM_RESPONSE)
        runner = EvaluationRunner(db_path=self.temp_db.name, llm_caller=mock_llm)
        metrics = runner.run()

        self.assertEqual(metrics["llm_calls_made"], 0)
        mock_llm.assert_not_called()

    def test_reuse_before_llm(self):
        """4. Verify reusable evaluation is detected before an LLM call occurs."""
        # Insert a pending job with identical company and description as disc_0001
        opp1 = self.repo.get_opportunity_by_id("disc_0001")
        self.repo.insert_opportunity({
            "id": "disc_t_dup",
            "title": opp1["title"],
            "company": opp1["company"],
            "location": "Mumbai, India",
            "description": opp1["description"],
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t_dup",
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
        })

        mock_llm = MagicMock(return_value=SAMPLE_MOCK_LLM_RESPONSE)
        runner = EvaluationRunner(db_path=self.temp_db.name, llm_caller=mock_llm)
        metrics = runner.run()

        self.assertEqual(metrics["reused_during_run"], 1)
        self.assertEqual(metrics["llm_calls_made"], 0)
        mock_llm.assert_not_called()

        reused_eval = self.repo.get_evaluation_by_opportunity_id("disc_t_dup")
        self.assertEqual(reused_eval["evaluation_status"], "REUSED")
        self.assertEqual(reused_eval["is_reused"], 1)

    def test_successful_evaluation_persisted(self):
        """5. Verify successful LLM response creates complete evaluation and updates status."""
        self.repo.insert_opportunity({
            "id": "disc_t_novel",
            "title": "Principal PM Payments",
            "company": "Razorpay Tech Labs",
            "location": "Bengaluru, India",
            "description": "Lead enterprise payments solutions.",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t_novel",
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
        })

        mock_llm = MagicMock(return_value=SAMPLE_MOCK_LLM_RESPONSE)
        runner = EvaluationRunner(db_path=self.temp_db.name, llm_caller=mock_llm, inter_call_delay=0.0)
        metrics = runner.run()

        self.assertEqual(metrics["fresh_evaluations_succeeded"], 1)
        self.assertEqual(metrics["llm_calls_made"], 1)

        ev = self.repo.get_evaluation_by_opportunity_id("disc_t_novel")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["evaluation_status"], "EVALUATED")
        self.assertEqual(ev["score"], 82.0)
        self.assertEqual(ev["recommendation"], "Apply")
        self.assertEqual(ev["fit_dimensions"]["role_fit"], 85)

    def test_failed_evaluation_not_marked_evaluated(self):
        """6. Verify failed response never becomes EVALUATED."""
        self.repo.insert_opportunity({
            "id": "disc_t_bad",
            "title": "Bad API Role",
            "company": "Broken API Corp",
            "location": "Bengaluru, India",
            "description": "Test bad API response.",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t_bad",
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
        })

        mock_llm = MagicMock(side_effect=RuntimeError("LLM API 500 internal error"))
        runner = EvaluationRunner(db_path=self.temp_db.name, llm_caller=mock_llm, inter_call_delay=0.0)
        metrics = runner.run()

        self.assertEqual(metrics["evaluations_failed"], 1)

        ev = self.repo.get_evaluation_by_opportunity_id("disc_t_bad")
        self.assertIsNotNone(ev)
        self.assertEqual(ev["evaluation_status"], "FAILED")
        self.assertIsNone(ev["score"])

    def test_resume_after_partial_run(self):
        """7. Verify already completed opportunities are skipped on restart."""
        # Insert 2 pending opportunities
        for idx in (1, 2):
            self.repo.insert_opportunity({
                "id": f"disc_t_res_{idx}",
                "title": f"Novel PM {idx}",
                "company": f"Unique Company {idx}",
                "location": "Bengaluru, India",
                "description": f"Unique PM role {idx}",
                "first_seen_run_id": "run_0002",
                "last_seen_run_id": "run_0002",
            })
            self.repo.insert_evaluation({
                "opportunity_id": f"disc_t_res_{idx}",
                "score": None,
                "recommendation": None,
                "evaluation_status": "PENDING",
            })

        mock_llm = MagicMock(return_value=SAMPLE_MOCK_LLM_RESPONSE)
        runner = EvaluationRunner(db_path=self.temp_db.name, llm_caller=mock_llm, inter_call_delay=0.0)

        # First run: process only 1 item
        m1 = runner.run(max_items=1)
        self.assertEqual(m1["fresh_evaluations_succeeded"], 1)
        self.assertEqual(m1["remaining_pending"], 1)

        # Second run: resumes and processes only the remaining 1 item
        m2 = runner.run()
        self.assertEqual(m2["pending_at_start"], 1)
        self.assertEqual(m2["fresh_evaluations_succeeded"], 1)
        self.assertEqual(m2["remaining_pending"], 0)

    def test_provider_failure_does_not_affect_evaluation_queue(self):
        """8. Verify discovery providers are not invoked by evaluation runner."""
        runner = EvaluationRunner(db_path=self.temp_db.name)
        # Verify runner only interacts with SQLite repository
        self.assertTrue(hasattr(runner, "repo"))
        self.assertFalse(hasattr(runner, "jobspy_adapter"))
        self.assertFalse(hasattr(runner, "jobspipe_adapter"))

    def test_null_score_not_zero(self):
        """9. Verify missing evaluation data remains NULL / pending rather than 0."""
        self.repo.insert_opportunity({
            "id": "disc_t_pending_only",
            "title": "Pending Only Role",
            "company": "Pending Co",
            "location": "Bengaluru, India",
            "description": "Job details",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })
        self.repo.insert_evaluation({
            "opportunity_id": "disc_t_pending_only",
            "score": None,
            "recommendation": None,
            "evaluation_status": "PENDING",
        })

        ws_data = self.repo.get_workstation_data()
        job = next(j for j in ws_data["jobs"] if j["job_id"] == "disc_t_pending_only")
        self.assertEqual(job["evaluation_status"], "PENDING")
        self.assertIsNone(job["llm_evaluation"])

    def test_historical_evaluations_unchanged(self):
        """10. Verify the 129 historical evaluations remain unchanged."""
        ev1 = self.repo.get_evaluation_by_opportunity_id("disc_0001")
        self.assertEqual(ev1["evaluation_status"], "EVALUATED")
        self.assertEqual(ev1["score"], 5.0)
        self.assertEqual(ev1["recommendation"], "Skip")


if __name__ == "__main__":
    unittest.main()
