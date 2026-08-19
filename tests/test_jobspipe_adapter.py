"""
tests/test_jobspipe_adapter.py — Unit tests for JobsPipe adapter, cross-provider deduplication, and provider isolation.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.adapters import (
    execute_jobspipe_adapter,
    execute_source_plan,
    STATUS_SUCCESS_WITH_RESULTS,
    STATUS_SUCCESS_EMPTY,
    STATUS_BLOCKED,
    STATUS_UNAVAILABLE,
    STATUS_TIMEOUT,
    STATUS_ERROR,
)
from career_os.discovery.normalizer import normalize_job, dedupe_jobs


class TestJobsPipeAdapter(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_jobspipe_sandbox_response_parsing(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        sample_payload = {
            "metadata": {
                "total_results": 1,
                "truncated_results": 1,
                "next_cursor": None,
            },
            "data": [
                {
                    "id": "jp_001",
                    "job_title": "Principal Product Manager",
                    "company": "Flipkart",
                    "company_domain": "flipkart.com",
                    "location": "Bengaluru, Karnataka, India",
                    "country_code": "IN",
                    "remote": False,
                    "date_posted": "2026-08-18",
                    "min_annual_salary_usd": 40000,
                    "max_annual_salary_usd": 60000,
                    "final_url": "https://flipkart.careers/job/jp_001",
                    "source_domain": "greenhouse.io",
                }
            ]
        }
        mock_resp.read.return_value = json.dumps(sample_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        records, status, err = execute_jobspipe_adapter(
            search_term="Principal Product Manager",
            country_code="IN",
            location="India",
            limit=5,
            use_sandbox=True,
        )

        self.assertEqual(status, STATUS_SUCCESS_WITH_RESULTS)
        self.assertIsNone(err)
        self.assertEqual(len(records), 1)

        raw = records[0]
        self.assertEqual(raw["title"], "Principal Product Manager")
        self.assertEqual(raw["company"], "Flipkart")
        self.assertEqual(raw["location"], "Bengaluru, Karnataka, India")
        self.assertEqual(raw["site"], "jobspipe")
        self.assertEqual(raw["source_domain"], "greenhouse.io")
        self.assertEqual(raw["_discovered_via_provider"], "jobspipe")

        norm = normalize_job(raw, {"search_query": "Principal PM"})
        self.assertEqual(norm["title"], "Principal Product Manager")
        self.assertIn("greenhouse.io", norm["provenance"]["sources"])
        self.assertIn("jobspipe", norm["provenance"]["providers"])
        self.assertEqual(norm["salary_min"], 40000)
        self.assertEqual(norm["currency"], "USD")

    @patch("urllib.request.urlopen")
    def test_jobspipe_empty_response(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"metadata": {"total_results": 0}, "data": []}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        records, status, err = execute_jobspipe_adapter(
            search_term="Obscure Title Nowhere Found",
            country_code="IN",
            use_sandbox=True,
        )

        self.assertEqual(status, STATUS_SUCCESS_EMPTY)
        self.assertEqual(len(records), 0)
        self.assertIsNone(err)

    @patch("urllib.request.urlopen")
    def test_jobspipe_documented_error_codes(self, mock_urlopen):
        # 401 Auth Error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.jobspipe.dev/v1/jobs/search",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )
        records, status, err = execute_jobspipe_adapter("PM", api_key="invalid_key", use_sandbox=False)
        self.assertEqual(status, STATUS_UNAVAILABLE)
        self.assertIn("401", err)

        # 402 Quota Exhausted
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.jobspipe.dev/v1/jobs/search",
            code=402,
            msg="Payment Required",
            hdrs={},
            fp=None,
        )
        records, status, err = execute_jobspipe_adapter("PM", api_key="key", use_sandbox=False)
        self.assertEqual(status, STATUS_UNAVAILABLE)
        self.assertIn("402", err)

        # 429 Rate Limit
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.jobspipe.dev/v1/jobs/search",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        records, status, err = execute_jobspipe_adapter("PM", api_key="key", use_sandbox=False)
        self.assertEqual(status, STATUS_UNAVAILABLE)
        self.assertIn("429", err)

    def test_cross_provider_deduplication(self):
        # JobSpy Indeed job
        jobspy_job = normalize_job({
            "title": "Fintech Product Manager",
            "company": "PhonePe",
            "location": "Bengaluru, Karnataka, India",
            "description": "Leading merchant payments and UPI settlement rails.",
            "job_url": "https://indeed.com/viewjob?jk=12345",
            "site": "indeed",
            "_discovered_via_provider": "jobspy",
            "min_amount": 2500000,
            "max_amount": 3500000,
            "date_posted": "2026-08-15",
        })

        # JobsPipe Greenhouse job for the SAME role
        jobspipe_job = normalize_job({
            "title": "Fintech Product Manager",
            "company": "PhonePe",
            "location": "Bengaluru, Karnataka, India",
            "description": "Leading merchant payments and UPI settlement rails with expanded detail.",
            "job_url": "https://boards.greenhouse.io/phonepe/jobs/999",
            "site": "greenhouse.io",
            "_discovered_via_provider": "jobspipe",
            "min_amount": 2500000,
            "max_amount": 3500000,
            "date_posted": "2026-08-14",
        })

        # Different job: same title & company, but in Gurugram
        different_location_job = normalize_job({
            "title": "Fintech Product Manager",
            "company": "PhonePe",
            "location": "Gurugram, Haryana, India",
            "description": "Gurugram office enterprise sales enablement role.",
            "job_url": "https://boards.greenhouse.io/phonepe/jobs/1000",
            "site": "greenhouse.io",
            "_discovered_via_provider": "jobspipe",
            "date_posted": "2026-08-16",
        })

        deduped = dedupe_jobs([jobspy_job, jobspipe_job, different_location_job])

        # Should produce 2 canonical opportunities:
        # 1 for Bengaluru (merged JobSpy + JobsPipe), 1 for Gurugram (distinct)
        self.assertEqual(len(deduped), 2)

        blr_job = next(j for j in deduped if "bengaluru" in j["location"].lower())
        self.assertIn("indeed", blr_job["provenance"]["sources"])
        self.assertIn("greenhouse.io", blr_job["provenance"]["sources"])
        self.assertIn("jobspy", blr_job["provenance"]["providers"])
        self.assertIn("jobspipe", blr_job["provenance"]["providers"])
        # Preserves earliest date
        self.assertEqual(blr_job["date_posted"], "2026-08-14")

        ggn_job = next(j for j in deduped if "gurugram" in j["location"].lower())
        self.assertEqual(ggn_job["location"], "Gurugram, Haryana, India")

    @patch("career_os.discovery.adapters.execute_jobspipe_adapter")
    @patch("jobspy.scrape_jobs")
    def test_provider_failure_isolation(self, mock_jobspy, mock_jobspipe):
        # Case 1: JobSpy fails with 429, JobsPipe succeeds
        mock_jobspy.side_effect = RuntimeError("JobSpy LinkedIn rate limit 429")
        mock_jobspipe.return_value = (
            [{"title": "AI PM", "company": "Swiggy", "location": "Bengaluru, IN", "site": "jobspipe", "_discovered_via_provider": "jobspipe"}],
            STATUS_SUCCESS_WITH_RESULTS,
            None
        )

        plan = [
            {"source": "linkedin", "adapter": "jobspy", "params": {"search_term": "AI PM"}, "intent": {"search_query": "AI PM"}},
            {"source": "jobspipe", "adapter": "jobspipe", "params": {"search_term": "AI PM"}, "intent": {"search_query": "AI PM"}},
        ]

        raw_jobs, health = execute_source_plan(plan, return_health_records=True)
        self.assertEqual(len(raw_jobs), 1)
        self.assertEqual(raw_jobs[0]["company"], "Swiggy")

        health_map = {h["source"]: h for h in health}
        self.assertEqual(health_map["linkedin"]["status"], STATUS_UNAVAILABLE)
        self.assertEqual(health_map["jobspipe"]["status"], STATUS_SUCCESS_WITH_RESULTS)


if __name__ == "__main__":
    unittest.main()
