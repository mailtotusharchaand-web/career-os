"""
tests/test_normalizer.py — Tests for canonical schema normalization, salary extraction, and multi-source deduplication.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.normalizer import normalize_job, dedupe_jobs, parse_salary_details


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

    def test_exact_deduplication_across_multiple_sources(self):
        raw_list = [
            {
                "title": "Staff Product Manager",
                "company": "Razorpay",
                "location": "Bengaluru, India",
                "site": "indeed",
                "date_posted": "2026-08-14",
                "description": "Short description",
                "job_url": "https://indeed.com/1",
            },
            {
                "title": "Staff Product Manager",
                "company": "Razorpay",
                "location": "Bengaluru, India",
                "site": "linkedin",
                "date_posted": "2026-08-12", # earlier date
                "description": "Longer detailed description with more information",
                "job_url": "https://linkedin.com/1",
            },
            {
                "title": "staff product manager",
                "company": "razorpay ",
                "location": "bengaluru, india",
                "site": "greenhouse",
                "date_posted": "2026-08-13",
                "description": "Greenhouse posting description",
                "job_url": "https://boards.greenhouse.io/razorpay/1",
            },
            {
                "title": "Data Analyst", # distinct role
                "company": "Razorpay",
                "location": "Bengaluru, India",
                "site": "naukri",
                "date_posted": "2026-08-15",
                "description": "Analytics role",
                "job_url": "https://naukri.com/2",
            }
        ]

        normalized = [normalize_job(j, {"search_query": "PM"}) for j in raw_list]
        deduped = dedupe_jobs(normalized)

        # 4 raw jobs should become 2 unique jobs
        self.assertEqual(len(deduped), 2)

        pm_job = next(j for j in deduped if j["title"].lower() == "staff product manager")
        # Check all 3 discovery sources preserved in provenance.sources
        self.assertEqual(sorted(pm_job["provenance"]["sources"]), ["greenhouse", "indeed", "linkedin"])
        # Check earliest date preserved
        self.assertEqual(pm_job["date_posted"], "2026-08-12")
        # Check longest description preserved
        self.assertIn("Longer detailed", pm_job["description"])

    def test_indian_salary_formats_and_bounds(self):
        # 1. Annual Rupee Range: ₹10,00,000 a year
        r1 = {"title": "PM", "company": "A", "description": "Salary: ₹10,00,000 a year"}
        n1 = normalize_job(r1)
        self.assertEqual(n1["salary_min"], 1000000)
        self.assertEqual(n1["salary_max"], 1000000)
        self.assertEqual(n1["salary_interval"], "yearly")
        self.assertEqual(n1["currency"], "INR")
        self.assertEqual(n1["salary_raw"], "₹10,00,000 a year")

        # 2. LPA Range: ₹8–12 LPA
        r2 = {"title": "PM", "company": "B", "description": "Compensation: ₹8–12 LPA"}
        n2 = normalize_job(r2)
        self.assertEqual(n2["salary_min"], 800000)
        self.assertEqual(n2["salary_max"], 1200000)
        self.assertEqual(n2["salary_interval"], "yearly")
        self.assertEqual(n2["currency"], "INR")

        # 3. Monthly Rupee: ₹50,000/month
        r3 = {"title": "PM", "company": "C", "description": "Pay: ₹50,000/month"}
        n3 = normalize_job(r3)
        self.assertEqual(n3["salary_min"], 50000)
        self.assertEqual(n3["salary_max"], 50000)
        self.assertEqual(n3["salary_interval"], "monthly")
        self.assertEqual(n3["currency"], "INR")

        # 4. Lakhs Range: 10-15 Lakhs
        r4 = {"title": "PM", "company": "D", "description": "CTC: 10-15 Lakhs per year"}
        n4 = normalize_job(r4)
        self.assertEqual(n4["salary_min"], 1000000)
        self.assertEqual(n4["salary_max"], 1500000)
        self.assertEqual(n4["salary_interval"], "yearly")
        self.assertEqual(n4["currency"], "INR")

        # 5. Missing / Malformed salary
        r5 = {"title": "PM", "company": "E", "description": "Great perks, coffee, and flexible hours."}
        n5 = normalize_job(r5)
        self.assertIsNone(n5["salary_min"])
        self.assertIsNone(n5["salary_max"])
        self.assertEqual(n5["salary_raw"], "")
        self.assertIsNone(n5["currency"])


if __name__ == "__main__":
    unittest.main()
