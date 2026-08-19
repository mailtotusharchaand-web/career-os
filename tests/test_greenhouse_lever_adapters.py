"""
tests/test_greenhouse_lever_adapters.py — Unit tests for Greenhouse and Lever ATS source adapters.
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
    execute_greenhouse_adapter,
    execute_lever_adapter,
    STATUS_SUCCESS_WITH_RESULTS,
    STATUS_SUCCESS_EMPTY,
    STATUS_BLOCKED,
    STATUS_UNAVAILABLE,
    STATUS_ERROR,
)
from career_os.discovery.normalizer import normalize_job


class TestGreenhouseLeverAdapters(unittest.TestCase):

    @patch("urllib.request.urlopen")
    def test_greenhouse_adapter_parsing_and_normalization(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        sample_greenhouse_payload = {
            "jobs": [
                {
                    "id": 4098273,
                    "title": "Senior Product Manager - Payments",
                    "location": {"name": "Bengaluru, Karnataka, India"},
                    "content": "Leading enterprise UPI payment pipelines and compliance.",
                    "absolute_url": "https://boards.greenhouse.io/razorpay/jobs/4098273",
                    "updated_at": "2026-08-18T10:00:00Z",
                },
                {
                    "id": 4098274,
                    "title": "Software Engineer US",
                    "location": {"name": "San Francisco, CA"},
                    "content": "Backend engineering role in SF.",
                    "absolute_url": "https://boards.greenhouse.io/razorpay/jobs/4098274",
                    "updated_at": "2026-08-18T10:00:00Z",
                }
            ]
        }
        mock_response.read.return_value = json.dumps(sample_greenhouse_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        records, status, err = execute_greenhouse_adapter(
            board_token="razorpay",
            search_term="Product Manager",
            location_filter="India",
        )

        self.assertEqual(status, STATUS_SUCCESS_WITH_RESULTS)
        self.assertIsNone(err)
        self.assertEqual(len(records), 1)

        raw = records[0]
        self.assertEqual(raw["title"], "Senior Product Manager - Payments")
        self.assertEqual(raw["site"], "greenhouse")
        self.assertEqual(raw["source_job_id"], "4098273")
        self.assertEqual(raw["date_posted"], "2026-08-18")

        norm = normalize_job(raw, {"search_query": "PM Payments"})
        self.assertEqual(norm["title"], "Senior Product Manager - Payments")
        self.assertEqual(norm["source"], "greenhouse")
        self.assertEqual(norm["provenance"]["sources"], ["greenhouse"])

    @patch("urllib.request.urlopen")
    def test_lever_adapter_parsing_and_normalization(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        sample_lever_payload = [
            {
                "id": "lev_98765",
                "text": "Lead Product Manager",
                "categories": {
                    "location": "Bengaluru",
                    "team": "Product",
                    "commitment": "Full-time",
                    "workplaceType": "hybrid",
                },
                "descriptionPlain": "Managing growth and onboarding flows for millions of merchants. CTC: Up to 35 LPA",
                "hostedUrl": "https://jobs.lever.co/groww/lev_98765",
                "createdAt": 1755500000000,
                "salaryRange": {
                    "min": 3000000,
                    "max": 3500000,
                    "interval": "yearly",
                    "currency": "INR",
                }
            }
        ]
        mock_response.read.return_value = json.dumps(sample_lever_payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        records, status, err = execute_lever_adapter(
            company_token="groww",
            search_term="Product Manager",
            location_filter="Bengaluru",
        )

        self.assertEqual(status, STATUS_SUCCESS_WITH_RESULTS)
        self.assertIsNone(err)
        self.assertEqual(len(records), 1)

        raw = records[0]
        self.assertEqual(raw["title"], "Lead Product Manager")
        self.assertEqual(raw["site"], "lever")
        self.assertEqual(raw["source_job_id"], "lev_98765")
        self.assertEqual(raw["min_amount"], 3000000)

        norm = normalize_job(raw, {"search_query": "Growth PM"})
        self.assertEqual(norm["title"], "Lead Product Manager")
        self.assertEqual(norm["salary_min"], 3000000)
        self.assertEqual(norm["salary_max"], 3500000)
        self.assertEqual(norm["currency"], "INR")

    @patch("urllib.request.urlopen")
    def test_adapter_http_error_handling(self, mock_urlopen):
        # 403 Forbidden
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://boards-api.greenhouse.io",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )
        records, status, err = execute_greenhouse_adapter("blocked_board")
        self.assertEqual(len(records), 0)
        self.assertEqual(status, STATUS_BLOCKED)


if __name__ == "__main__":
    unittest.main()
