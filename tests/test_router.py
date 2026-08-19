"""
tests/test_router.py — Tests for source capability routing for India.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.router import route_intent, load_source_registry


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.registry = {
            "sources": {
                "indeed": {
                    "adapter": "jobspy",
                    "geographic_coverage": ["global", "IN"],
                    "supports_location_param": True,
                    "supports_country_param": True,
                    "country_code_map": {"IN": "india"},
                    "enabled": True,
                },
                "naukri": {
                    "adapter": "jobspy",
                    "geographic_coverage": ["IN"],
                    "supports_location_param": True,
                    "supports_country_param": False,
                    "enabled": True,
                },
                "linkedin": {
                    "adapter": "jobspy",
                    "geographic_coverage": ["global", "IN"],
                    "supports_location_param": True,
                    "supports_country_param": False,
                    "enabled": True,
                },
                "disabled_source": {
                    "adapter": "jobspy",
                    "geographic_coverage": ["IN"],
                    "enabled": False,
                }
            }
        }

    def test_routes_india_intent_to_india_capable_sources(self):
        intent = {
            "search_query": "Product Manager",
            "location_intent": "India",
            "country_code": "IN",
        }
        plan = route_intent(intent, self.registry)
        source_names = [p["source"] for p in plan]
        self.assertIn("indeed", source_names)
        self.assertIn("naukri", source_names)
        self.assertIn("linkedin", source_names)
        self.assertNotIn("disabled_source", source_names)

    def test_source_parameters_for_indeed_india(self):
        intent = {
            "search_query": "Digital Product Manager",
            "location_intent": "Bengaluru",
            "country_code": "IN",
        }
        plan = route_intent(intent, self.registry)
        indeed_plan = next(p for p in plan if p["source"] == "indeed")
        self.assertEqual(indeed_plan["params"].get("country_indeed"), "india")
        self.assertEqual(indeed_plan["params"].get("search_term"), "Digital Product Manager")

    def test_source_parameters_for_linkedin_india(self):
        intent = {
            "search_query": "Product Manager",
            "location_intent": "India",
            "country_code": "IN",
        }
        plan = route_intent(intent, self.registry)
        linkedin_plan = next(p for p in plan if p["source"] == "linkedin")
        self.assertEqual(linkedin_plan["params"].get("location"), "India")


if __name__ == "__main__":
    unittest.main()
