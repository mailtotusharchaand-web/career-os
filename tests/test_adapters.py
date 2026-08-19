"""
tests/test_adapters.py — Tests for source adapter execution and failure isolation.
"""

import unittest
from unittest.mock import patch
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.adapters import execute_source_plan


class TestAdapters(unittest.TestCase):
    def test_source_failure_isolation(self):
        """If LinkedIn raises an exception, Indeed and Naukri must still succeed."""
        execution_plan = [
            {"source": "indeed", "params": {"search_term": "Product Manager", "country_indeed": "india"}},
            {"source": "linkedin", "params": {"search_term": "Product Manager", "location": "India"}},
            {"source": "naukri", "params": {"search_term": "Product Manager"}},
        ]

        def mock_scrape(site_name, **kwargs):
            if site_name == ["linkedin"] or site_name == "linkedin":
                raise RuntimeError("LinkedIn rate limit 429")
            import pandas as pd
            return pd.DataFrame([
                {"title": f"Job from {site_name}", "company": "Acme", "location": "Bengaluru, India", "site": site_name[0] if isinstance(site_name, list) else site_name}
            ])

        with patch("jobspy.scrape_jobs", side_effect=mock_scrape):
            raw_jobs, errors = execute_source_plan(execution_plan)

        # LinkedIn failed, but we got results from indeed and naukri!
        self.assertEqual(len(raw_jobs), 2)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["source"], "linkedin")
        self.assertIn("429", errors[0]["error"])


if __name__ == "__main__":
    unittest.main()
