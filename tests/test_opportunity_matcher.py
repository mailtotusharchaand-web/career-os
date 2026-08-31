"""
tests.test_opportunity_matcher — Unit tests for deterministic multi-signal opportunity matching.
"""

import unittest
from career_os.email.models import RawEmailMessage, EmailClassification, EventType, ConfidenceLevel
from career_os.email.matcher import OpportunityMatcher


class TestOpportunityMatcher(unittest.TestCase):
    def setUp(self):
        self.sample_opportunities = [
            {
                "id": "disc_0001",
                "title": "Principal PM Payments",
                "normalized_title": "principal pm payments",
                "company": "Razorpay",
                "normalized_company": "razorpay",
                "location": "Bengaluru, Karnataka, India",
                "description": "Lead payments platform architecture. Requisition ID: RZP-PAY-882.",
                "job_url": "https://careers.razorpay.com/jobs/882",
            },
            {
                "id": "disc_0002",
                "title": "Senior Product Manager - Growth",
                "normalized_title": "senior product manager growth",
                "company": "Swiggy",
                "normalized_company": "swiggy",
                "location": "Bengaluru, Karnataka, India",
                "description": "Drive top-of-funnel customer acquisition. Req: SWG-9921",
                "job_url": "https://swiggy.careers/growth-pm",
            },
            {
                "id": "disc_0003",
                "title": "Staff Engineer - Backend",
                "normalized_title": "staff engineer backend",
                "company": "Flipkart",
                "normalized_company": "flipkart",
                "location": "Bengaluru, India",
                "description": "Distributed systems engineering.",
                "job_url": "https://flipkart.com/careers/backend-staff",
            },
            {
                "id": "disc_0004",
                "title": "Staff Engineer - Frontend",
                "normalized_title": "staff engineer frontend",
                "company": "Flipkart",
                "normalized_company": "flipkart",
                "location": "Bengaluru, India",
                "description": "Web client performance engineering.",
                "job_url": "https://flipkart.com/careers/frontend-staff",
            },
        ]
        self.matcher = OpportunityMatcher(self.sample_opportunities)

    def test_match_by_requisition_id(self):
        msg = RawEmailMessage(
            provider="mock",
            account_id="user@example.com",
            message_id="m1",
            thread_id="t1",
            sender="Swiggy <jobs@swiggy.in>",
            recipients=["user@example.com"],
            subject="Your Application SWG-9921",
            body_text="Thank you for applying for the role. Requisition SWG-9921.",
            received_at="2026-08-31T10:00:00Z",
        )
        classification = EmailClassification(
            event_type=EventType.APPLICATION_CONFIRMATION,
            confidence_score=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable_state_transition=True,
            reasoning="App confirm",
            detected_company="Swiggy",
            detected_requisition_id="SWG-9921",
        )
        res = self.matcher.match(msg, classification)
        self.assertEqual(res.opportunity_id, "disc_0002")
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)
        self.assertIn("exact_requisition_id", res.match_signals)

    def test_match_by_exact_company_and_role(self):
        msg = RawEmailMessage(
            provider="mock",
            account_id="user@example.com",
            message_id="m2",
            thread_id="t2",
            sender="Razorpay Talent <talent@razorpay.com>",
            recipients=["user@example.com"],
            subject="Interview for Principal PM Payments",
            body_text="We invite you to interview for Principal PM Payments at Razorpay.",
            received_at="2026-08-31T10:00:00Z",
        )
        classification = EmailClassification(
            event_type=EventType.INTERVIEW_INVITATION,
            confidence_score=0.95,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable_state_transition=True,
            reasoning="Interview invite",
            detected_company="Razorpay",
            detected_role="Principal PM Payments",
        )
        res = self.matcher.match(msg, classification)
        self.assertEqual(res.opportunity_id, "disc_0001")
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)

    def test_ambiguous_match_across_multiple_company_roles(self):
        # Flipkart has both Backend and Frontend Staff Engineer in sample DB
        msg = RawEmailMessage(
            provider="mock",
            account_id="user@example.com",
            message_id="m3",
            thread_id="t3",
            sender="Flipkart Careers <careers@flipkart.com>",
            recipients=["user@example.com"],
            subject="Update on your application at Flipkart",
            body_text="Thank you for your application to Flipkart. Our hiring managers are reviewing it.",
            received_at="2026-08-31T10:00:00Z",
        )
        classification = EmailClassification(
            event_type=EventType.APPLICATION_UPDATE,
            confidence_score=0.75,
            confidence_level=ConfidenceLevel.MEDIUM,
            is_actionable_state_transition=False,
            reasoning="App update",
            detected_company="Flipkart",
            detected_role=None,
        )
        res = self.matcher.match(msg, classification)
        # Should be AMBIGUOUS and not auto-bind to a single opportunity
        self.assertEqual(res.confidence_level, ConfidenceLevel.AMBIGUOUS)
        self.assertIsNone(res.opportunity_id)
        self.assertTrue(len(res.candidate_matches) >= 2)

    def test_unmatched_job_does_not_invent_opportunity(self):
        msg = RawEmailMessage(
            provider="mock",
            account_id="user@example.com",
            message_id="m4",
            thread_id="t4",
            sender="Unknown Startup <hiring@unknownstartup.xyz>",
            recipients=["user@example.com"],
            subject="Application Acknowledgement for Designer",
            body_text="Thank you for applying for Lead Product Designer at Unknown Startup.",
            received_at="2026-08-31T10:00:00Z",
        )
        classification = EmailClassification(
            event_type=EventType.APPLICATION_CONFIRMATION,
            confidence_score=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable_state_transition=True,
            reasoning="App confirm",
            detected_company="Unknown Startup",
            detected_role="Lead Product Designer",
        )
        res = self.matcher.match(msg, classification)
        self.assertIsNone(res.opportunity_id)
        self.assertEqual(res.confidence_level, ConfidenceLevel.LOW)


if __name__ == "__main__":
    unittest.main()
