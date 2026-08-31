"""
tests.test_lifecycle_engine — Unit tests for application lifecycle validation and anti-regression rules.
"""

import unittest
from career_os.email.lifecycle import LifecycleValidator
from career_os.email.models import EventType, ConfidenceLevel, EventStatus


class TestLifecycleEngine(unittest.TestCase):
    def test_valid_forward_transitions(self):
        # 1. NOT_APPLIED -> APPLIED via APPLICATION_CONFIRMATION
        dec = LifecycleValidator.evaluate_transition(
            current_status="NOT_APPLIED",
            event_type=EventType.APPLICATION_CONFIRMATION,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertTrue(dec.is_legal)
        self.assertTrue(dec.should_mutate)
        self.assertEqual(dec.proposed_status, "APPLIED")
        self.assertEqual(dec.event_status, EventStatus.AUTOMATIC_APPLIED)

        # 2. APPLIED -> INTERVIEW via INTERVIEW_INVITATION
        dec2 = LifecycleValidator.evaluate_transition(
            current_status="APPLIED",
            event_type=EventType.INTERVIEW_INVITATION,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertTrue(dec2.is_legal)
        self.assertTrue(dec2.should_mutate)
        self.assertEqual(dec2.proposed_status, "INTERVIEW")

        # 3. INTERVIEW -> OFFER via OFFER
        dec3 = LifecycleValidator.evaluate_transition(
            current_status="INTERVIEW",
            event_type=EventType.OFFER,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertTrue(dec3.is_legal)
        self.assertTrue(dec3.should_mutate)
        self.assertEqual(dec3.proposed_status, "OFFER")

        # 4. APPLIED -> REJECTED via REJECTION
        dec4 = LifecycleValidator.evaluate_transition(
            current_status="APPLIED",
            event_type=EventType.REJECTION,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertTrue(dec4.is_legal)
        self.assertTrue(dec4.should_mutate)
        self.assertEqual(dec4.proposed_status, "REJECTED")

    def test_anti_regression_protection(self):
        # 1. INTERVIEW must NEVER regress to APPLIED from late confirmation email
        dec = LifecycleValidator.evaluate_transition(
            current_status="INTERVIEW",
            event_type=EventType.APPLICATION_CONFIRMATION,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertFalse(dec.is_legal)
        self.assertFalse(dec.should_mutate)
        self.assertEqual(dec.proposed_status, "INTERVIEW")  # Preserved!
        self.assertIn("Anti-regression", dec.reason)

        # 2. OFFER must NEVER regress to APPLIED
        dec2 = LifecycleValidator.evaluate_transition(
            current_status="OFFER",
            event_type=EventType.APPLICATION_CONFIRMATION,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertFalse(dec2.is_legal)
        self.assertFalse(dec2.should_mutate)
        self.assertEqual(dec2.proposed_status, "OFFER")  # Preserved!

        # 3. OFFER must NEVER regress to INTERVIEW
        dec3 = LifecycleValidator.evaluate_transition(
            current_status="OFFER",
            event_type=EventType.INTERVIEW_INVITATION,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )
        self.assertFalse(dec3.is_legal)
        self.assertFalse(dec3.should_mutate)
        self.assertEqual(dec3.proposed_status, "OFFER")  # Preserved!

    def test_evidence_only_events_do_not_mutate(self):
        # Amendment 2: ASSESSMENT_REQUEST creates evidence without mutating state
        dec_assess = LifecycleValidator.evaluate_transition(
            current_status="APPLIED",
            event_type=EventType.ASSESSMENT_REQUEST,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=False,
        )
        self.assertTrue(dec_assess.is_legal)
        self.assertFalse(dec_assess.should_mutate)  # No mutation!
        self.assertEqual(dec_assess.proposed_status, "APPLIED")
        self.assertIn("timeline evidence", dec_assess.reason)

        # Amendment 3: RECRUITER_CONTACT creates evidence without mutating state
        dec_rec = LifecycleValidator.evaluate_transition(
            current_status="NOT_APPLIED",
            event_type=EventType.RECRUITER_CONTACT,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=False,
        )
        self.assertTrue(dec_rec.is_legal)
        self.assertFalse(dec_rec.should_mutate)  # No mutation!
        self.assertEqual(dec_rec.proposed_status, "NOT_APPLIED")

    def test_ambiguous_confidence_does_not_mutate(self):
        dec_amb = LifecycleValidator.evaluate_transition(
            current_status="NOT_APPLIED",
            event_type=EventType.APPLICATION_CONFIRMATION,
            confidence_level=ConfidenceLevel.AMBIGUOUS,
            is_actionable=True,
        )
        self.assertFalse(dec_amb.is_legal)
        self.assertFalse(dec_amb.should_mutate)
        self.assertEqual(dec_amb.event_status, EventStatus.PENDING_CONFIRMATION)


if __name__ == "__main__":
    unittest.main()
