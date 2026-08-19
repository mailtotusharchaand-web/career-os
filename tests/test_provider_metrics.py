"""
tests/test_provider_metrics.py — Regression and invariant tests for provider contribution and duplicate accounting.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from discover_india import compute_discovery_metrics
from career_os.discovery.normalizer import normalize_job, dedupe_jobs


class TestProviderMetricsAccounting(unittest.TestCase):

    def test_jobspy_jobspipe_duplicate_accounting_regression(self):
        """
        Regression test specifically for the 80 JobSpy + 10 JobsPipe controlled discovery scenario:
        - JobSpy: 80 raw -> 70 unique (10 intra-provider duplicates)
        - JobsPipe: 10 raw -> 6 unique (4 intra-provider duplicates)
        - Combined provider unique: 76
        - Cross-provider overlap: 1
        - Final unique: 75
        - Total duplicates merged: 15 (14 intra-provider + 1 cross-provider)
        """
        raw_jobspy = []
        for i in range(70):
            raw_jobspy.append({
                "title": f"JobSpy Role {i}",
                "company": f"Company {i}",
                "location": "Bengaluru, India",
                "site": "indeed",
                "_discovered_via_source": "indeed",
                "_discovered_via_provider": "jobspy",
            })
        # 10 intra-JobSpy duplicates
        for i in range(10):
            raw_jobspy.append({
                "title": f"JobSpy Role {i}",
                "company": f"Company {i}",
                "location": "Bengaluru, India",
                "site": "linkedin",
                "_discovered_via_source": "linkedin",
                "_discovered_via_provider": "jobspy",
            })

        raw_jobspipe = []
        # 1 overlapping role with JobSpy
        raw_jobspipe.append({
            "title": "JobSpy Role 0",
            "company": "Company 0",
            "location": "Bengaluru, India",
            "site": "jobspipe",
            "_discovered_via_source": "jobspipe",
            "_discovered_via_provider": "jobspipe",
        })
        # 5 distinct JobsPipe roles
        for i in range(1, 6):
            raw_jobspipe.append({
                "title": f"JobsPipe Novel Role {i}",
                "company": f"Novel Company {i}",
                "location": "Bengaluru, India",
                "site": "jobspipe",
                "_discovered_via_source": "jobspipe",
                "_discovered_via_provider": "jobspipe",
            })
        # 4 intra-JobsPipe duplicates
        for i in range(1, 5):
            raw_jobspipe.append({
                "title": f"JobsPipe Novel Role {i}",
                "company": f"Novel Company {i}",
                "location": "Bengaluru, India",
                "site": "jobspipe",
                "_discovered_via_source": "jobspipe",
                "_discovered_via_provider": "jobspipe",
            })

        all_raw = raw_jobspy + raw_jobspipe
        norm_all = [normalize_job(r) for r in all_raw]
        final_deduped = dedupe_jobs(norm_all)

        m = compute_discovery_metrics(all_raw, final_deduped)

        self.assertEqual(m["total_raw_records"], 90)
        self.assertEqual(m["provider_unique_records_total"], 76)
        self.assertEqual(m["intra_provider_duplicates"], 14)
        self.assertEqual(m["cross_provider_duplicates"], 1)
        self.assertEqual(m["total_duplicates_merged"], 15)
        self.assertEqual(m["final_unique_records"], 75)
        self.assertEqual(m["jobspy_only"], 69)
        self.assertEqual(m["jobspipe_only"], 5)
        self.assertEqual(m["found_by_both"], 1)

        # Provider-specific breakdown
        self.assertEqual(m["provider_metrics"]["jobspy"]["raw"], 80)
        self.assertEqual(m["provider_metrics"]["jobspy"]["unique"], 70)
        self.assertEqual(m["provider_metrics"]["jobspy"]["duplicates"], 10)

        self.assertEqual(m["provider_metrics"]["jobspipe"]["raw"], 10)
        self.assertEqual(m["provider_metrics"]["jobspipe"]["unique"], 6)
        self.assertEqual(m["provider_metrics"]["jobspipe"]["duplicates"], 4)

        # Fundamental Invariants
        self.assertEqual(m["total_raw_records"] - m["total_duplicates_merged"], m["final_unique_records"])
        self.assertEqual(m["total_raw_records"], m["final_unique_records"] + m["total_duplicates_merged"])

    def test_zero_duplicates_scenario(self):
        """When all records from all providers are completely unique."""
        raw_jobs = [
            {"title": f"Role A{i}", "company": f"Comp A{i}", "location": "India", "site": "indeed", "_discovered_via_provider": "jobspy"}
            for i in range(5)
        ] + [
            {"title": f"Role B{i}", "company": f"Comp B{i}", "location": "India", "site": "jobspipe", "_discovered_via_provider": "jobspipe"}
            for i in range(5)
        ]
        norm = [normalize_job(r) for r in raw_jobs]
        deduped = dedupe_jobs(norm)

        m = compute_discovery_metrics(raw_jobs, deduped)

        self.assertEqual(m["total_raw_records"], 10)
        self.assertEqual(m["provider_unique_records_total"], 10)
        self.assertEqual(m["intra_provider_duplicates"], 0)
        self.assertEqual(m["cross_provider_duplicates"], 0)
        self.assertEqual(m["total_duplicates_merged"], 0)
        self.assertEqual(m["final_unique_records"], 10)
        self.assertEqual(m["jobspy_only"], 5)
        self.assertEqual(m["jobspipe_only"], 5)
        self.assertEqual(m["found_by_both"], 0)
        self.assertEqual(m["total_raw_records"] - m["total_duplicates_merged"], m["final_unique_records"])

    def test_complete_cross_provider_overlap(self):
        """When all records from JobsPipe are exact duplicates of JobSpy records."""
        raw_jobspy = [
            {"title": f"Role {i}", "company": f"Comp {i}", "location": "India", "site": "indeed", "_discovered_via_provider": "jobspy"}
            for i in range(5)
        ]
        raw_jobspipe = [
            {"title": f"Role {i}", "company": f"Comp {i}", "location": "India", "site": "jobspipe", "_discovered_via_provider": "jobspipe"}
            for i in range(5)
        ]
        all_raw = raw_jobspy + raw_jobspipe
        norm = [normalize_job(r) for r in all_raw]
        deduped = dedupe_jobs(norm)

        m = compute_discovery_metrics(all_raw, deduped)

        self.assertEqual(m["total_raw_records"], 10)
        self.assertEqual(m["provider_unique_records_total"], 10)
        self.assertEqual(m["intra_provider_duplicates"], 0)
        self.assertEqual(m["cross_provider_duplicates"], 5)
        self.assertEqual(m["total_duplicates_merged"], 5)
        self.assertEqual(m["final_unique_records"], 5)
        self.assertEqual(m["jobspy_only"], 0)
        self.assertEqual(m["jobspipe_only"], 0)
        self.assertEqual(m["found_by_both"], 5)
        self.assertEqual(m["total_raw_records"] - m["total_duplicates_merged"], m["final_unique_records"])


if __name__ == "__main__":
    unittest.main()
