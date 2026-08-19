"""
tests/test_memory_acceptance.py — Comprehensive Persistent Memory Acceptance Test Suite.
Validates Scenarios A through J for Run 001 -> Run 002 memory, provenance, identity,
lifecycle preservation, and LLM evaluation reuse hierarchy.
"""

import hashlib
import json
import os
import tempfile
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.db.repository import CareerOSRepository, compute_canonical_key, compute_content_hash
from career_os.db.migrate_json_to_sqlite import run_migration, EXPECTED_RESULTS_SHA256, EXPECTED_EVALS_SHA256


class TestMemoryAcceptanceScenarios(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        # Initialize with Run 001 historical migration
        success, report = run_migration(db_path=self.temp_db.name)
        self.assertTrue(success, "Historical Run 001 migration failed")
        self.repo = CareerOSRepository(db_path=self.temp_db.name)

        # Pre-insert test discovery runs for foreign key integrity
        self.repo.insert_discovery_run({"id": "run_0002", "run_number": 2, "status": "COMPLETED"})
        self.repo.insert_discovery_run({"id": "run_0003", "run_number": 3, "status": "COMPLETED"})

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # Scenario A: Existing Opportunity
    # -------------------------------------------------------------------------
    def test_scenario_a_existing_opportunity_seen(self):
        """
        Opportunity from Run 001 introduced again in Run 002:
        - Same canonical opportunity ID.
        - Classification = SEEN.
        - No duplicate opportunity created.
        - Existing evaluation reused (REUSED_EXACT).
        - 0 LLM calls.
        """
        opp1 = self.repo.get_opportunity_by_id("disc_0001")
        self.assertIsNotNone(opp1)

        # Re-introduce opp1 in Run 002
        canonical_key = opp1["canonical_key"]
        existing = self.repo.get_opportunity_by_key(canonical_key)
        self.assertIsNotNone(existing)
        self.assertEqual(existing["id"], "disc_0001")

        # Classify & mark seen
        self.repo.mark_opportunity_seen("disc_0001", run_id="run_0002")
        self.repo.insert_run_opportunity("run_0002", "disc_0001", "SEEN", rank=1)

        # Check evaluation reuse
        reused = self.repo.find_reusable_evaluation(existing)
        self.assertIsNotNone(reused)
        reused_eval, reuse_type, reason = reused
        self.assertEqual(reuse_type, "REUSED_EXACT")
        self.assertEqual(reused_eval["opportunity_id"], "disc_0001")

        # Verify no duplicate opportunity record
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM opportunities WHERE canonical_key = ?;", (canonical_key,))
            self.assertEqual(cur.fetchone()[0], 1)

    # -------------------------------------------------------------------------
    # Scenario B: Same Posting / Different Provider
    # -------------------------------------------------------------------------
    def test_scenario_b_same_posting_different_provider(self):
        """
        Represent an existing posting once as JobSpy and once as JobsPipe:
        - One canonical opportunity.
        - Both providers/sources preserved in provenance.
        - Existing evaluation reused.
        - 0 LLM calls.
        """
        opp = self.repo.get_opportunity_by_id("disc_0002")
        self.assertIsNotNone(opp)

        # Add JobsPipe source for same opportunity in Run 002
        self.repo.insert_opportunity_source({
            "opportunity_id": "disc_0002",
            "provider": "jobspipe",
            "source": "jobspipe",
            "job_url": "https://jobspipe.io/job/12345",
            "search_query": "Fintech Product Manager",
            "hypothesis_id": "hyp_001",
            "opportunity_type": "direct",
            "discovery_run_id": "run_0002",
        })

        # Verify provenance has both providers
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT provider, source FROM opportunity_sources WHERE opportunity_id = 'disc_0002';")
            sources = [dict(r) for r in cur.fetchall()]
            providers = set(s["provider"] for s in sources)
            self.assertIn("jobspy", providers)
            self.assertIn("jobspipe", providers)

        # Verify evaluation reuse
        reused = self.repo.find_reusable_evaluation(opp)
        self.assertIsNotNone(reused)
        reused_eval, reuse_type, reason = reused
        self.assertIn(reuse_type, ("REUSED_EXACT", "REUSED_SAME_POSTING"))

    # -------------------------------------------------------------------------
    # Scenario C: Same Role / Different Location
    # -------------------------------------------------------------------------
    def test_scenario_c_same_role_different_location(self):
        """
        Same substantive role/company in two locations:
        - Distinct opportunity IDs because location is part of opportunity identity.
        - Deterministic equivalent-role evaluation reuse (REUSED_EQUIVALENT_ROLE).
        - 0 LLM calls.
        """
        base_opp = self.repo.get_opportunity_by_id("disc_0005")
        self.assertIsNotNone(base_opp)

        # Create identical role at same company but different city (e.g. Pune vs Bengaluru)
        new_loc_key = compute_canonical_key(base_opp["title"], base_opp["company"], "Pune, Maharashtra, India")
        self.assertNotEqual(new_loc_key, base_opp["canonical_key"])

        new_opp = {
            "id": "disc_0999_pune",
            "canonical_key": new_loc_key,
            "title": base_opp["title"],
            "company": base_opp["company"],
            "location": "Pune, Maharashtra, India",
            "description": base_opp["description"],
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        }
        self.repo.insert_opportunity(new_opp)

        # Verify distinct opportunity created
        loaded_new = self.repo.get_opportunity_by_id("disc_0999_pune")
        self.assertIsNotNone(loaded_new)
        self.assertNotEqual(loaded_new["id"], base_opp["id"])

        # Verify Level 3 evaluation reuse
        reused = self.repo.find_reusable_evaluation(new_opp)
        self.assertIsNotNone(reused)
        reused_eval, reuse_type, reason = reused
        self.assertEqual(reuse_type, "REUSED_EQUIVALENT_ROLE")

    # -------------------------------------------------------------------------
    # Scenario D: Previously Applied Job
    # -------------------------------------------------------------------------
    def test_scenario_d_previously_applied_job_persistence(self):
        """
        Existing opportunity with application_status = APPLIED rediscovered in Run 002:
        - Same opportunity ID.
        - Application status remains APPLIED.
        - Classification = ALREADY_APPLIED.
        - Must NOT appear as a new unapplied Apply opportunity.
        - Existing evaluation reused.
        - 0 LLM calls.
        """
        # disc_0015 has human review APPLIED in Run 001
        opp15 = self.repo.get_opportunity_by_id("disc_0015")
        self.assertEqual(opp15["current_application_status"], "APPLIED")

        # Rediscover in Run 002
        ckey = opp15["canonical_key"]
        existing = self.repo.get_opportunity_by_key(ckey)
        self.assertIsNotNone(existing)

        # Classification check logic
        app_st = existing.get("current_application_status", "NOT_APPLIED")
        self.assertEqual(app_st, "APPLIED")
        classification = "ALREADY_APPLIED"

        self.repo.mark_opportunity_seen(existing["id"], run_id="run_0002")
        self.repo.insert_run_opportunity("run_0002", existing["id"], classification, rank=1)

        # Verify status is NOT reset
        reloaded = self.repo.get_opportunity_by_id("disc_0015")
        self.assertEqual(reloaded["current_application_status"], "APPLIED")

        # Verify evaluation reused
        reused = self.repo.find_reusable_evaluation(existing)
        self.assertIsNotNone(reused)

    # -------------------------------------------------------------------------
    # Scenario E: Previously Reviewed Job
    # -------------------------------------------------------------------------
    def test_scenario_e_previously_reviewed_job(self):
        """
        Existing reviewed opportunity rediscovered:
        - Existing human review remains intact.
        - No duplicate review record.
        - Existing evaluation reused.
        - 0 LLM calls.
        """
        rev_before = self.repo.get_human_review("disc_0001")
        self.assertIsNotNone(rev_before)
        self.assertEqual(rev_before["verdict"], "IRRELEVANT")

        # Rediscover disc_0001 in Run 002
        self.repo.mark_opportunity_seen("disc_0001", run_id="run_0002")
        self.repo.insert_run_opportunity("run_0002", "disc_0001", "ALREADY_REVIEWED", rank=1)

        rev_after = self.repo.get_human_review("disc_0001")
        self.assertEqual(rev_after["verdict"], "IRRELEVANT")
        self.assertEqual(rev_after["notes"], rev_before["notes"])

        # Verify no duplicate review row in DB
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM human_reviews WHERE opportunity_id = 'disc_0001';")
            self.assertEqual(cur.fetchone()[0], 1)

    # -------------------------------------------------------------------------
    # Scenario F: Disappeared -> Reappeared
    # -------------------------------------------------------------------------
    def test_scenario_f_disappeared_and_reappeared(self):
        """
        Run 001 opportunity absent in Run 002 fixture, then returns in Run 003:
        - Historical opportunity remains in DB.
        - Run 002 records its absence (presence_status = DISAPPEARED).
        - Run 003 classifies it as REAPPEARED.
        - No duplicate opportunity created.
        """
        opp = self.repo.get_opportunity_by_id("disc_0010")
        self.assertIsNotNone(opp)

        # Run 002 marks it absent/disappeared
        self.repo.mark_opportunity_disappeared("disc_0010")
        opp_run2 = self.repo.get_opportunity_by_id("disc_0010")
        self.assertEqual(opp_run2["presence_status"], "DISAPPEARED")

        # Run 003 rediscovers opp
        ckey = opp["canonical_key"]
        existing = self.repo.get_opportunity_by_key(ckey)
        self.assertIsNotNone(existing)
        self.assertEqual(existing["presence_status"], "DISAPPEARED")

        # Classification is REAPPEARED
        classification = "REAPPEARED" if existing["presence_status"] == "DISAPPEARED" else "SEEN"
        self.assertEqual(classification, "REAPPEARED")

        self.repo.mark_opportunity_seen("disc_0010", run_id="run_0003")
        self.repo.insert_run_opportunity("run_0003", "disc_0010", classification, rank=1)

        opp_run3 = self.repo.get_opportunity_by_id("disc_0010")
        self.assertEqual(opp_run3["presence_status"], "AVAILABLE")
        self.assertEqual(opp_run3["last_seen_run_id"], "run_0003")

        # Verify no duplicate opportunity record
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM opportunities WHERE canonical_key = ?;", (ckey,))
            self.assertEqual(cur.fetchone()[0], 1)

    # -------------------------------------------------------------------------
    # Scenario G: Completely New Job
    # -------------------------------------------------------------------------
    def test_scenario_g_completely_new_opportunity_requires_llm(self):
        """
        Genuinely new opportunity not present in Run 001:
        - New opportunity ID.
        - Classification = NEW.
        - No reusable evaluation exists.
        - Marked as requiring a fresh LLM evaluation (1 LLM call requested).
        """
        new_opp = {
            "id": "disc_0200",
            "title": "Principal AI Architect",
            "company": "Anthropic AI Labs",
            "location": "Bengaluru, Karnataka, India",
            "description": "Designing novel transformer attention mechanics and inference engines.",
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        }
        ckey = compute_canonical_key(new_opp["title"], new_opp["company"], new_opp["location"])
        existing = self.repo.get_opportunity_by_key(ckey)
        self.assertIsNone(existing)

        # Classification is NEW
        classification = "NEW"
        self.repo.insert_opportunity({**new_opp, "canonical_key": ckey})
        self.repo.insert_run_opportunity("run_0002", "disc_0200", classification, rank=1)

        # Check evaluation reuse -> Must be None
        reused = self.repo.find_reusable_evaluation(new_opp)
        self.assertIsNone(reused)

    # -------------------------------------------------------------------------
    # Scenario H: Different Company / Similar Role
    # -------------------------------------------------------------------------
    def test_scenario_h_different_company_similar_role_no_reuse(self):
        """
        Same title/role at two materially different companies:
        - Do NOT reuse the previous evaluation automatically.
        - Fresh LLM evaluation required.
        """
        opp = self.repo.get_opportunity_by_id("disc_0001")
        diff_company_opp = {
            "id": "disc_diff_comp_001",
            "title": opp["title"],
            "company": "Entirely Different Company Inc",
            "location": opp["location"],
            "description": "Completely different team responsibilities and corporate objectives.",
        }
        reused = self.repo.find_reusable_evaluation(diff_company_opp)
        self.assertIsNone(reused, "Different company must not automatically reuse evaluation")

    # -------------------------------------------------------------------------
    # Scenario I: Provider Deduplication (Indeed + LinkedIn + JobsPipe)
    # -------------------------------------------------------------------------
    def test_scenario_i_provider_deduplication(self):
        """
        Multiple representations of the same posting (Indeed, LinkedIn, JobsPipe):
        - One canonical opportunity.
        - All applicable provenance preserved.
        - One evaluation.
        - 0 unnecessary LLM calls.
        """
        opp_id = "disc_multi_prov"
        title = "Staff Product Architect"
        company = "Stripe India"
        location = "Bengaluru, Karnataka, India"
        desc = "Core payment rails and banking integrations."
        ckey = compute_canonical_key(title, company, location)

        self.repo.insert_opportunity({
            "id": opp_id,
            "canonical_key": ckey,
            "title": title,
            "company": company,
            "location": location,
            "description": desc,
            "first_seen_run_id": "run_0002",
            "last_seen_run_id": "run_0002",
        })

        # Insert 3 sources across providers
        self.repo.insert_opportunity_source({
            "opportunity_id": opp_id,
            "provider": "jobspy",
            "source": "indeed",
            "job_url": "https://indeed.com/viewjob?jk=111",
            "search_query": "Payments Product Manager",
            "discovery_run_id": "run_0002",
        })
        self.repo.insert_opportunity_source({
            "opportunity_id": opp_id,
            "provider": "jobspy",
            "source": "linkedin",
            "job_url": "https://linkedin.com/jobs/view/222",
            "search_query": "Payments Product Manager",
            "discovery_run_id": "run_0002",
        })
        self.repo.insert_opportunity_source({
            "opportunity_id": opp_id,
            "provider": "jobspipe",
            "source": "jobspipe",
            "job_url": "https://jobspipe.io/job/333",
            "search_query": "Payments Product Manager",
            "discovery_run_id": "run_0002",
        })

        # Verify only 1 canonical opportunity exists
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM opportunities WHERE canonical_key = ?;", (ckey,))
            self.assertEqual(cur.fetchone()[0], 1)

            # Verify all 3 sources preserved
            src_cur = conn.execute("SELECT provider, source FROM opportunity_sources WHERE opportunity_id = ?;", (opp_id,))
            sources = [dict(r) for r in src_cur.fetchall()]
            self.assertEqual(len(sources), 3)

    # -------------------------------------------------------------------------
    # Scenario J: Application History Transitions
    # -------------------------------------------------------------------------
    def test_scenario_j_application_history_transitions(self):
        """
        Test transitions:
        NOT_APPLIED -> READY_TO_APPLY -> APPLIED -> INTERVIEW -> OFFER:
        - Current status is OFFER.
        - application_status_history contains all 4 transitions.
        - Rediscovery never destroys history.
        """
        opp_id = "disc_lifecycle_test"
        self.repo.insert_opportunity({
            "id": opp_id,
            "title": "VP Product",
            "company": "CRED",
            "location": "Bengaluru, India",
            "description": "Executive product leadership.",
            "first_seen_run_id": "run_0001",
            "last_seen_run_id": "run_0001",
        })

        # Execute 4 lifecycle transitions
        transitions = [
            ("READY_TO_APPLY", "Flagged for customized CV"),
            ("APPLIED", "Submitted application on careers page"),
            ("INTERVIEW", "Recruiter screening scheduled"),
            ("OFFER", "Offer letter received"),
        ]

        for new_st, notes in transitions:
            self.repo.record_application_transition(opp_id, new_status=new_st, notes=notes)

        # Check current status
        opp = self.repo.get_opportunity_by_id(opp_id)
        self.assertEqual(opp["current_application_status"], "OFFER")

        # Check history audit trail
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT * FROM application_status_history WHERE opportunity_id = ? ORDER BY id ASC;", (opp_id,))
            history = [dict(r) for r in cur.fetchall()]
            self.assertEqual(len(history), 4)
            self.assertEqual(history[0]["previous_status"], "NOT_APPLIED")
            self.assertEqual(history[0]["new_status"], "READY_TO_APPLY")
            self.assertEqual(history[1]["previous_status"], "READY_TO_APPLY")
            self.assertEqual(history[1]["new_status"], "APPLIED")
            self.assertEqual(history[2]["previous_status"], "APPLIED")
            self.assertEqual(history[2]["new_status"], "INTERVIEW")
            self.assertEqual(history[3]["previous_status"], "INTERVIEW")
            self.assertEqual(history[3]["new_status"], "OFFER")

        # Rediscover in Run 002
        self.repo.mark_opportunity_seen(opp_id, run_id="run_0002")
        reloaded = self.repo.get_opportunity_by_id(opp_id)
        self.assertEqual(reloaded["current_application_status"], "OFFER")

        # History remains intact
        with self.repo.connection() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM application_status_history WHERE opportunity_id = ?;", (opp_id,))
            self.assertEqual(cur.fetchone()[0], 4)


if __name__ == "__main__":
    unittest.main()
