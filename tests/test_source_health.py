"""
tests/test_source_health.py — Unit tests for source execution health reporting and failure isolation.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.adapters import (
    execute_source_plan,
    STATUS_SUCCESS_WITH_RESULTS,
    STATUS_SUCCESS_EMPTY,
    STATUS_BLOCKED,
    STATUS_ERROR,
    STATUS_TIMEOUT,
    STATUS_UNAVAILABLE,
)


class TestSourceHealth(unittest.TestCase):

    @patch("jobspy.scrape_jobs")
    def test_source_health_success_with_results(self, mock_scrape):
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.to_dict.return_value = [{"title": "PM", "company": "Co", "location": "Bengaluru, IN"}]
        mock_scrape.return_value = mock_df

        plan = [{"source": "indeed", "adapter": "jobspy", "params": {"search_term": "PM"}, "intent": {"search_query": "PM"}}]
        raw_jobs, health_records = execute_source_plan(plan, return_health_records=True)

        self.assertEqual(len(raw_jobs), 1)
        self.assertEqual(len(health_records), 1)
        self.assertEqual(health_records[0]["status"], STATUS_SUCCESS_WITH_RESULTS)
        self.assertEqual(health_records[0]["results_count"], 1)
        self.assertIsNone(health_records[0]["error"])

    @patch("jobspy.scrape_jobs")
    def test_source_health_success_empty(self, mock_scrape):
        mock_df = MagicMock()
        mock_df.empty = True
        mock_scrape.return_value = mock_df

        plan = [{"source": "naukri", "adapter": "jobspy", "params": {"search_term": "Obscure Title"}, "intent": {"search_query": "Obscure Title"}}]
        raw_jobs, health_records = execute_source_plan(plan, return_health_records=True)

        self.assertEqual(len(raw_jobs), 0)
        self.assertEqual(len(health_records), 1)
        self.assertEqual(health_records[0]["status"], STATUS_SUCCESS_EMPTY)
        self.assertEqual(health_records[0]["results_count"], 0)
        self.assertIsNone(health_records[0]["error"])

    @patch("jobspy.scrape_jobs")
    def test_source_health_blocked_and_failure_isolation(self, mock_scrape):
        def side_effect(site_name, **kwargs):
            if site_name == ["linkedin"]:
                raise Exception("LinkedIn rate limit 429: Too Many Requests")
            elif site_name == ["naukri"]:
                raise Exception("Naukri bot block: HTTP 403 Forbidden Cloudflare challenge")
            elif site_name == ["indeed"]:
                df = MagicMock()
                df.empty = False
                df.to_dict.return_value = [{"title": "Fintech PM", "company": "Razorpay", "location": "Bengaluru, IN"}]
                return df
            raise Exception("Unknown site")

        mock_scrape.side_effect = side_effect

        plan = [
            {"source": "indeed", "adapter": "jobspy", "params": {"search_term": "Fintech"}, "intent": {"search_query": "Fintech"}},
            {"source": "linkedin", "adapter": "jobspy", "params": {"search_term": "Fintech"}, "intent": {"search_query": "Fintech"}},
            {"source": "naukri", "adapter": "jobspy", "params": {"search_term": "Fintech"}, "intent": {"search_query": "Fintech"}},
        ]

        raw_jobs, health_records = execute_source_plan(plan, return_health_records=True)

        self.assertEqual(len(raw_jobs), 1)
        self.assertEqual(raw_jobs[0]["company"], "Razorpay")
        self.assertEqual(len(health_records), 3)

        health_map = {h["source"]: h for h in health_records}
        self.assertEqual(health_map["indeed"]["status"], STATUS_SUCCESS_WITH_RESULTS)
        self.assertEqual(health_map["linkedin"]["status"], STATUS_UNAVAILABLE)
        self.assertEqual(health_map["naukri"]["status"], STATUS_BLOCKED)


if __name__ == "__main__":
    unittest.main()
