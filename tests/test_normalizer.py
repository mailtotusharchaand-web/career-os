"""
tests/test_normalizer.py — Tests for canonical schema normalization and deterministic exact deduplication.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.normalizer import normalize_job, dedupe_jobs


class TestNormalizer(unittest.TestCase):
    def test_normalize_job_schema(self):
        raw = {
            "title": "Digital Product Manager",
            "company": "American Express",
            "location": "Gurugram, India",
            "description": "Managing enterprise payment workflows...",
            "job_url": "https://example.com/job/123",
            "site": "linkedin",
            "date_posted": "2026-08-15",
            "job_type": "fulltime",
        }
        query_context = {
            "search_query": "Digital Product Manager",
        }
        normalized = normalize_job(raw, query_context)
        
        # Verify required fields
        self.assertEqual(normalized["title"], "Digital Product Manager")
        self.assertEqual(normalized["company"], "American Express")
        self.assertEqual(normalized["location"], "Gurugram, India")
        self.assertEqual(normalized["source"], "linkedin")
        self.assertEqual(normalized["provenance"]["sources"], ["linkedin"])
        self.assertEqual(normalized["provenance"]["search_query"], "Digital Product Manager")
        self.assertTrue("retrieved_at" in normalized["provenance"])

    def test_exact_deduplication_across_sources(self):
        raw_list = [
            {
                "title": "Product Manager",
                "company": "Swiggy",
                "location": "Bengaluru, India",
                "site": "indeed",
                "date_posted": "2026-08-14",
                "description": "Short description",
                "job_url": "https://indeed.com/1",
            },
            {
                "title": "product manager",  # lowercase
                "company": "Swiggy ",        # trailing space
                "location": "Bengaluru, India",
                "site": "linkedin",
                "date_posted": "2026-08-12", # earlier date
                "description": "Longer detailed description with more information",
                "job_url": "https://linkedin.com/1",
            },
            {
                "title": "Data Analyst",     # distinct role
                "company": "Swiggy",
                "location": "Bengaluru, India",
                "site": "naukri",
                "date_posted": "2026-08-15",
                "description": "Analytics role",
                "job_url": "https://naukri.com/2",
            }
        ]

        normalized = [normalize_job(j, {"search_query": "PM"}) for j in raw_list]
        deduped = dedupe_jobs(normalized)

        # 3 raw jobs should become 2 unique jobs
        self.assertEqual(len(deduped), 2)

        pm_job = next(j for j in deduped if j["title"].lower() == "product manager")
        # Check merged sources
        self.assertIn("indeed", pm_job["provenance"]["sources"])
        self.assertIn("linkedin", pm_job["provenance"]["sources"])
        # Check earliest date preserved
        self.assertEqual(pm_job["date_posted"], "2026-08-12")
        # Check longer description preserved
        self.assertIn("Longer detailed", pm_job["description"])


if __name__ == "__main__":
    unittest.main()
