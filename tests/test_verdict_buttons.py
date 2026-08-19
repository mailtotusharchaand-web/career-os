"""
tests/test_verdict_buttons.py — Regression tests for all 4 discovery verdict options:
RELEVANT, ADJACENT, WEAK, and IRRELEVANT.
"""

import unittest
import json
import tempfile
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from review_server import save_discovery_decisions, load_discovery_decisions, compute_discovery_summary


class TestVerdictButtons(unittest.TestCase):
    def test_all_four_verdicts_can_be_selected_and_saved(self):
        """Verify that RELEVANT, ADJACENT, WEAK, and IRRELEVANT are all valid and saved correctly."""
        verdicts = ["RELEVANT", "ADJACENT", "WEAK", "IRRELEVANT"]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "discovery_human_review_test.json"
            
            decisions = {}
            for idx, verdict in enumerate(verdicts, 1):
                job_id = f"disc_{idx:04d}"
                decisions[job_id] = {
                    "job_id": job_id,
                    "verdict": verdict,
                    "counterfactual": "NO",
                    "notes": f"Testing {verdict} selection",
                    "opportunity_type": "direct",
                    "search_query": "Fintech Product Manager",
                    "source": "indeed",
                }

            save_discovery_decisions({"decisions": decisions}, file_path=test_file)
            loaded = load_discovery_decisions(file_path=test_file)

            self.assertEqual(len(loaded["decisions"]), 4)
            for idx, verdict in enumerate(verdicts, 1):
                job_id = f"disc_{idx:04d}"
                self.assertIn(job_id, loaded["decisions"])
                self.assertEqual(loaded["decisions"][job_id]["verdict"], verdict)

    def test_irrelevant_verdict_in_summary_calculation(self):
        """Verify that IRRELEVANT verdict is accurately tallied in discovery summary stats."""
        mock_jobs = [
            {"job_id": "disc_0001", "source": "indeed", "provenance": {"opportunity_type": "direct", "search_query": "PM"}},
            {"job_id": "disc_0002", "source": "indeed", "provenance": {"opportunity_type": "direct", "search_query": "PM"}},
        ]
        mock_decisions = {
            "disc_0001": {"job_id": "disc_0001", "verdict": "IRRELEVANT", "counterfactual": "NO"},
            "disc_0002": {"job_id": "disc_0002", "verdict": "RELEVANT", "counterfactual": "YES"},
        }
        summary = compute_discovery_summary(mock_jobs, mock_decisions)
        self.assertEqual(summary["verdicts"]["IRRELEVANT"], 1)
        self.assertEqual(summary["verdicts"]["RELEVANT"], 1)
        self.assertEqual(summary["by_opportunity_type"]["direct"]["IRRELEVANT"], 1)
        self.assertEqual(summary["by_opportunity_type"]["direct"]["RELEVANT"], 1)


if __name__ == "__main__":
    unittest.main()
