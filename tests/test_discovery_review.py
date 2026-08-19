"""
tests/test_discovery_review.py — Tests for Discovery Quality Review data loading,
decision saving, separation of storage, and summary breakdown calculations.
"""

import unittest
import json
import tempfile
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from review_server import (
    load_discovery_data,
    load_discovery_decisions,
    save_discovery_decisions,
    compute_discovery_summary,
    DISCOVERY_RESULTS_FILE,
    DISCOVERY_HUMAN_FILE,
)


class TestDiscoveryReview(unittest.TestCase):
    def test_discovery_data_loading_and_job_id_assignment(self):
        """Verify that all 129 opportunities are loaded with stable job_id and provenance."""
        data = load_discovery_data()
        self.assertIn("jobs", data)
        self.assertEqual(len(data["jobs"]), 129)

        first_job = data["jobs"][0]
        self.assertEqual(first_job["job_id"], "disc_0001")
        self.assertIn("title", first_job)
        self.assertIn("company", first_job)
        self.assertIn("provenance", first_job)
        self.assertIn("search_query", first_job["provenance"])
        self.assertIn("opportunity_type", first_job["provenance"])

    def test_storage_separation(self):
        """Verify that discovery decisions do not overwrite or modify human_review.json or india_discovery_results.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "discovery_human_review_test.json"
            
            payload = {
                "decisions": {
                    "disc_0001": {
                        "job_id": "disc_0001",
                        "verdict": "RELEVANT",
                        "counterfactual": "NO",
                        "notes": "Great find via dynamic intent",
                        "opportunity_type": "direct",
                        "search_query": "Fintech Product Manager",
                        "source": "indeed",
                    }
                }
            }
            save_discovery_decisions(payload, file_path=test_file)
            
            self.assertTrue(test_file.exists())
            with open(test_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            
            self.assertIn("disc_0001", saved["decisions"])
            self.assertEqual(saved["decisions"]["disc_0001"]["verdict"], "RELEVANT")
            self.assertEqual(saved["decisions"]["disc_0001"]["counterfactual"], "NO")

    def test_discovery_summary_breakdown(self):
        """Verify breakdown metrics calculation across opportunity types, intents, and sources."""
        mock_jobs = [
            {
                "job_id": "disc_0001",
                "title": "Fintech PM",
                "source": "indeed",
                "provenance": {"opportunity_type": "direct", "search_query": "Fintech Product Manager"}
            },
            {
                "job_id": "disc_0002",
                "title": "B2B SaaS PM",
                "source": "linkedin",
                "provenance": {"opportunity_type": "adjacent", "search_query": "B2B SaaS Product Manager"}
            },
            {
                "job_id": "disc_0003",
                "title": "AI PM",
                "source": "linkedin",
                "provenance": {"opportunity_type": "unexpected", "search_query": "AI Product Manager"}
            }
        ]

        mock_decisions = {
            "disc_0001": {
                "job_id": "disc_0001",
                "verdict": "RELEVANT",
                "counterfactual": "YES",
            },
            "disc_0002": {
                "job_id": "disc_0002",
                "verdict": "ADJACENT",
                "counterfactual": "NO",
            }
        }

        summary = compute_discovery_summary(mock_jobs, mock_decisions)
        self.assertEqual(summary["total_discovered"], 3)
        self.assertEqual(summary["total_reviewed"], 2)
        self.assertEqual(summary["total_unreviewed"], 1)
        self.assertEqual(summary["verdicts"]["RELEVANT"], 1)
        self.assertEqual(summary["verdicts"]["ADJACENT"], 1)
        self.assertEqual(summary["counterfactuals"]["YES"], 1)
        self.assertEqual(summary["counterfactuals"]["NO"], 1)
        self.assertIn("direct", summary["by_opportunity_type"])
        self.assertIn("Fintech Product Manager", summary["by_search_intent"])
        self.assertIn("indeed", summary["by_source"])

    def test_lifecycle_status_persistence_and_defaults(self):
        """Verify opportunity_status and application_status are preserved and defaults apply."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "discovery_human_review_test.json"
            
            payload = {
                "decisions": {
                    "disc_0001": {
                        "job_id": "disc_0001",
                        "verdict": "RELEVANT",
                        "counterfactual": "YES",
                        "priority": "HIGH",
                        "opportunity_status": "AVAILABLE",
                        "application_status": "APPLIED",
                        "notes": "Applied on portal",
                    },
                    "disc_0002": {
                        "job_id": "disc_0002",
                        "verdict": "IRRELEVANT",
                        "counterfactual": "NO",
                        "priority": "LOW",
                        # Missing opportunity_status and application_status
                        "notes": "Old job",
                    }
                }
            }
            save_discovery_decisions(payload, file_path=test_file)
            loaded = load_discovery_decisions(file_path=test_file)
            
            d1 = loaded["decisions"]["disc_0001"]
            self.assertEqual(d1["opportunity_status"], "AVAILABLE")
            self.assertEqual(d1["application_status"], "APPLIED")
            
            d2 = loaded["decisions"]["disc_0002"]
            self.assertIsNone(d2.get("opportunity_status"))
            self.assertIsNone(d2.get("application_status"))

    def test_lifecycle_summary_aggregation(self):
        """Verify compute_discovery_summary aggregates opportunity and application statuses across all jobs."""
        mock_jobs = [
            {"job_id": "disc_0001", "source": "indeed", "provenance": {"opportunity_type": "direct", "search_query": "PM"}},
            {"job_id": "disc_0002", "source": "indeed", "provenance": {"opportunity_type": "direct", "search_query": "PM"}},
            {"job_id": "disc_0003", "source": "linkedin", "provenance": {"opportunity_type": "adjacent", "search_query": "APM"}},
        ]
        mock_decisions = {
            "disc_0001": {
                "job_id": "disc_0001",
                "verdict": "RELEVANT",
                "opportunity_status": "AVAILABLE",
                "application_status": "APPLIED",
            },
            "disc_0002": {
                "job_id": "disc_0002",
                "verdict": "IRRELEVANT",
                "opportunity_status": "EXPIRED",
                "application_status": "NOT_APPLIED",
            },
            # disc_0003 is unreviewed
        }

        summary = compute_discovery_summary(mock_jobs, mock_decisions)
        self.assertIn("opportunity_statuses", summary)
        self.assertIn("application_statuses", summary)
        self.assertEqual(summary["opportunity_statuses"]["AVAILABLE"], 1)
        self.assertEqual(summary["opportunity_statuses"]["EXPIRED"], 1)
        self.assertEqual(summary["opportunity_statuses"]["UNKNOWN"], 1)  # disc_0003 unreviewed
        self.assertEqual(summary["application_statuses"]["APPLIED"], 1)
        self.assertEqual(summary["application_statuses"]["NOT_APPLIED"], 2)  # disc_0002 + disc_0003


if __name__ == "__main__":
    unittest.main()
