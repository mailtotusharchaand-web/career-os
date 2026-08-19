"""
tests/test_geography.py — Tests for India location recognition and token-aware parsing.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.geography import is_india_location, normalize_location


class TestGeography(unittest.TestCase):
    def test_explicit_india_suffix(self):
        cases = [
            "Bengaluru, India",
            "Bangalore, India",
            "Gurugram, India",
            "Gurgaon, India",
            "Mumbai, India",
            "Hyderabad, India",
            "Pune, India",
            "Chennai, India",
            "Delhi, India",
            "Noida, India",
            "Remote - India",
            "India",
        ]
        for loc in cases:
            with self.subTest(location=loc):
                self.assertTrue(is_india_location(loc), f"Failed for {loc}")
                res = normalize_location(loc)
                self.assertEqual(res["country_code"], "IN")

    def test_indian_state_codes_from_jobspy(self):
        # JobSpy Indeed scraper often returns "KA, IN", "TS, IN", "GA, IN", "MH, IN", "Remote, IN"
        cases = [
            "KA, IN",
            "TS, IN",
            "GA, IN",
            "MH, IN",
            "DL, IN",
            "HR, IN",
            "Remote, IN",
        ]
        for loc in cases:
            with self.subTest(location=loc):
                self.assertTrue(is_india_location(loc), f"Failed for {loc}")
                res = normalize_location(loc)
                self.assertEqual(res["country_code"], "IN")

    def test_indianapolis_is_not_india(self):
        # Indianapolis, IN must be US (Indiana), NOT India
        loc = "Indianapolis, IN"
        self.assertFalse(is_india_location(loc), f"{loc} was incorrectly identified as India!")
        res = normalize_location(loc)
        self.assertEqual(res["country_code"], "US")

    def test_other_us_and_international_locations(self):
        cases = [
            ("New York, NY", "US"),
            ("Portland, OR", "US"),
            ("London, UK", "GB"),
            ("Austin, TX", "US"),
        ]
        for loc, expected_country in cases:
            with self.subTest(location=loc):
                self.assertFalse(is_india_location(loc))
                res = normalize_location(loc)
                self.assertEqual(res["country_code"], expected_country)

    def test_empty_or_unknown_location(self):
        self.assertFalse(is_india_location(""))
        self.assertFalse(is_india_location(None))
        res = normalize_location("")
        self.assertEqual(res["country_code"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
