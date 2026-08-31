"""
tests.test_email_classifier — Unit tests for layered email classification and domain guardrails.
"""

import unittest
from career_os.email.models import RawEmailMessage, EventType, ConfidenceLevel
from career_os.email.classifier import EmailClassifier


class TestEmailClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = EmailClassifier()

    def _make_msg(self, subject: str, body: str, sender: str = "talent@company.com") -> RawEmailMessage:
        return RawEmailMessage(
            provider="mock",
            account_id="user@example.com",
            message_id="msg_test",
            thread_id="th_test",
            sender=sender,
            recipients=["user@example.com"],
            subject=subject,
            body_text=body,
            received_at="2026-08-31T12:00:00Z",
        )

    def test_application_confirmation(self):
        msg = self._make_msg(
            subject="Thank you for applying to Swiggy - Product Manager",
            body="We have received your application for the Product Manager role. Thank you for your interest!",
            sender="Swiggy Careers <no-reply@swiggy.in>",
        )
        res = self.classifier.classify(msg)
        self.assertEqual(res.event_type, EventType.APPLICATION_CONFIRMATION)
        self.assertTrue(res.is_actionable_state_transition)
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)

    def test_interview_invitation(self):
        msg = self._make_msg(
            subject="Invitation to Interview with Razorpay",
            body="We would like to schedule an interview with our engineering director. Please pick a slot.",
            sender="Razorpay Recruiting <talent@razorpay.com>",
        )
        res = self.classifier.classify(msg)
        self.assertEqual(res.event_type, EventType.INTERVIEW_INVITATION)
        self.assertTrue(res.is_actionable_state_transition)
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)

    def test_assessment_request_is_evidence_only(self):
        # Amendment 2: ASSESSMENT_REQUEST is timeline evidence only; not actionable state transition to INTERVIEW
        msg = self._make_msg(
            subject="PhonePe: Complete the Technical Assessment",
            body="Please complete the HackerRank online assessment within 48 hours for the PM position.",
            sender="HackerRank <support@hackerrank.com>",
        )
        res = self.classifier.classify(msg)
        self.assertEqual(res.event_type, EventType.ASSESSMENT_REQUEST)
        self.assertFalse(res.is_actionable_state_transition)  # Amendment 2 verified!
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)

    def test_rejection_notice(self):
        msg = self._make_msg(
            subject="Update on your application at CRED",
            body="After careful consideration, unfortunately we will not be moving forward with your application.",
            sender="CRED Careers <careers@cred.club>",
        )
        res = self.classifier.classify(msg)
        self.assertEqual(res.event_type, EventType.REJECTION)
        self.assertTrue(res.is_actionable_state_transition)
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)

    def test_offer_letter(self):
        msg = self._make_msg(
            subject="Offer of Employment - Flipkart",
            body="We are delighted to offer you the position of Staff Product Manager at Flipkart. Official offer letter attached.",
            sender="Flipkart Talent <offers@flipkart.com>",
        )
        res = self.classifier.classify(msg)
        self.assertEqual(res.event_type, EventType.OFFER)
        self.assertTrue(res.is_actionable_state_transition)
        self.assertEqual(res.confidence_level, ConfidenceLevel.HIGH)

    def test_recruiter_contact_is_evidence_only(self):
        # Amendment 3: RECRUITER_CONTACT does NOT mutate application state
        msg = self._make_msg(
            subject="Exploring Opportunities at Zomato",
            body="I came across your profile and was impressed by your work. Would you be open to exploring opportunities?",
            sender="Recruiter <recruiter@zomato.com>",
        )
        res = self.classifier.classify(msg)
        self.assertEqual(res.event_type, EventType.RECRUITER_CONTACT)
        self.assertFalse(res.is_actionable_state_transition)  # Amendment 3 verified!

    def test_irrelevant_job_alerts_and_otp(self):
        alert_msg = self._make_msg(
            subject="15 New Jobs in Bengaluru for you",
            body="Daily job digest. Click here to view jobs recommended for you. Unsubscribe.",
            sender="Naukri Alerts <alerts@naukri.com>",
        )
        res_alert = self.classifier.classify(alert_msg)
        self.assertEqual(res_alert.event_type, EventType.IRRELEVANT)
        self.assertFalse(res_alert.is_actionable_state_transition)

        otp_msg = self._make_msg(
            subject="Your Google verification code",
            body="Your one-time password (OTP) is 482910.",
            sender="Google Security <no-reply@accounts.google.com>",
        )
        res_otp = self.classifier.classify(otp_msg)
        self.assertEqual(res_otp.event_type, EventType.IRRELEVANT)
        self.assertFalse(res_otp.is_actionable_state_transition)


if __name__ == "__main__":
    unittest.main()
