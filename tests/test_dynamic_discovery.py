"""
tests/test_dynamic_discovery.py — Tests for dynamic capability extraction,
opportunity hypotheses generation, search intent validation, and budget guardrails.
"""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.candidate_model import validate_capability_model
from career_os.discovery.hypotheses import validate_hypotheses
from career_os.discovery.intents import validate_and_filter_intents, dedupe_intents


class TestDynamicDiscovery(unittest.TestCase):
    def test_capability_model_schema_conformance(self):
        valid_model = {
            "candidate_summary": "Experienced product and analytics professional.",
            "capabilities": [
                {
                    "capability": "Process Analytics & Defect Reduction",
                    "evidence": ["Led RCA on 500K+ interactions at Amazon"],
                    "proficiency": "demonstrated",
                    "recency": "recent",
                    "transferable_context": "Operational efficiency across enterprise domains",
                },
                {
                    "capability": "Cross-Border Regulatory Compliance",
                    "evidence": ["Managed Belgium KYC rollout across 3 systems"],
                    "proficiency": "demonstrated",
                    "recency": "recent",
                    "transferable_context": "Complex multi-system compliance workflows",
                }
            ],
            "responsibilities": ["Backlog prioritization", "UAT leadership"],
            "domain_exposure": ["Enterprise payments", "Customer experience analytics"],
            "tools_and_technologies": ["SQL", "Python", "PEGA/ACE", "Jira"],
            "business_problems_solved": ["Reduced manual effort by 20% via automation"]
        }
        validated = validate_capability_model(valid_model)
        self.assertIn("capabilities", validated)
        self.assertEqual(len(validated["capabilities"]), 2)
        self.assertEqual(validated["capabilities"][0]["proficiency"], "demonstrated")

    def test_capability_model_invalid_structure(self):
        invalid_model = {"random_key": "not a capability model"}
        with self.assertRaises(ValueError):
            validate_capability_model(invalid_model)

    def test_hypotheses_validation_and_capability_references(self):
        valid_hypotheses = [
            {
                "hypothesis_id": "hyp_001",
                "hypothesis": "Enterprise Workflow Optimization Product Lead",
                "rationale": "Strong background in high-volume case management and defect RCA.",
                "supporting_capabilities": ["Process Analytics & Defect Reduction"],
                "evidence": "Amazon and Amex platform operations.",
                "opportunity_type": "adjacent",
            },
            {
                "hypothesis_id": "hyp_002",
                "hypothesis": "Fintech Compliance Platform Specialist",
                "rationale": "Direct experience with KYC/AML cross-border rollouts.",
                "supporting_capabilities": ["Cross-Border Regulatory Compliance"],
                "evidence": "Belgium KYC project.",
                "opportunity_type": "direct",
            }
        ]
        validated = validate_hypotheses(valid_hypotheses)
        self.assertEqual(len(validated), 2)
        self.assertEqual(validated[0]["opportunity_type"], "adjacent")

    def test_hypotheses_invalid_items_skipped(self):
        mixed_hypotheses = [
            {
                "hypothesis_id": "hyp_001",
                "hypothesis": "Valid Hypothesis",
                "rationale": "Has supporting evidence",
                "supporting_capabilities": ["Capability 1"],
                "evidence": "CV line 12",
                "opportunity_type": "transferable",
            },
            {
                "hypothesis_id": "hyp_bad",
                "missing_fields": True  # Should be filtered out or raise
            }
        ]
        validated = validate_hypotheses(mixed_hypotheses)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0]["hypothesis_id"], "hyp_001")

    def test_search_intents_enforce_india_only(self):
        raw_intents = [
            {
                "search_query": "Digital Product Manager",
                "country_code": "IN",
                "location_intent": "India",
                "hypothesis_id": "hyp_001",
                "rationale": "Direct search",
            },
            {
                "search_query": "Product Manager US",
                "country_code": "US",  # INTERNATIONAL - MUST BE REJECTED
                "location_intent": "United States",
                "hypothesis_id": "hyp_001",
                "rationale": "International query",
            },
            {
                "search_query": "Compliance Analyst UK",
                "country_code": "GB",  # INTERNATIONAL - MUST BE REJECTED
                "location_intent": "London",
                "hypothesis_id": "hyp_002",
                "rationale": "International query",
            },
            {
                "search_query": "Process Analytics Specialist",
                "country_code": "IN",
                "location_intent": "India",
                "hypothesis_id": "hyp_002",
                "rationale": "Operational query",
            }
        ]
        filtered = validate_and_filter_intents(raw_intents, max_budget=10)
        self.assertEqual(len(filtered), 2)
        for intent in filtered:
            self.assertEqual(intent["country_code"], "IN")
            self.assertEqual(intent["location_intent"], "India")

    def test_search_intents_deduplication(self):
        intents = [
            {"search_query": "Digital Product Manager", "country_code": "IN", "location_intent": "India", "hypothesis_id": "hyp_001"},
            {"search_query": "digital product manager ", "country_code": "IN", "location_intent": "India", "hypothesis_id": "hyp_002"},
            {"search_query": "Risk Analyst", "country_code": "IN", "location_intent": "India", "hypothesis_id": "hyp_003"},
        ]
        deduped = dedupe_intents(intents)
        self.assertEqual(len(deduped), 2)
        queries = [i["search_query"].strip().lower() for i in deduped]
        self.assertEqual(queries, ["digital product manager", "risk analyst"])

    def test_search_intents_budget_limit(self):
        intents = [
            {"search_query": f"Query {i}", "country_code": "IN", "location_intent": "India", "hypothesis_id": f"hyp_{i}"}
            for i in range(25)
        ]
        filtered = validate_and_filter_intents(intents, max_budget=8)
        self.assertEqual(len(filtered), 8)


if __name__ == "__main__":
    unittest.main()
