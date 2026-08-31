"""
career_os.email.lifecycle — Application Lifecycle Transition Validator & Anti-Regression Engine.

Enforces strict state progression rules:
- State Hierarchy: NOT_APPLIED (0) < READY_TO_APPLY (1) < APPLIED (2) < INTERVIEW (3) < OFFER (4)
- Anti-Regression: Out-of-order application confirmations or interview invites cannot regress higher states (OFFER, INTERVIEW).
- Evidence vs Transition Distinction: ASSESSMENT_REQUEST and RECRUITER_CONTACT are preserved as evidence without mutating state.
- Ambiguous matches never mutate state automatically.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from .models import EventType, ConfidenceLevel, EventStatus


STATE_RANK = {
    "NOT_APPLIED": 0,
    "READY_TO_APPLY": 1,
    "RECRUITER_CONTACT": 1,
    "APPLIED": 2,
    "INTERVIEW": 3,
    "OFFER": 4,
    "REJECTED": 5,
    "WITHDRAWN": 5,
}


@dataclass
class TransitionDecision:
    is_legal: bool
    should_mutate: bool
    current_status: str
    proposed_status: str
    event_status: EventStatus
    reason: str


class LifecycleValidator:
    """Validates whether an incoming CareerEvent can legally mutate an opportunity's application status."""

    @staticmethod
    def evaluate_transition(
        current_status: Optional[str],
        event_type: EventType,
        confidence_level: ConfidenceLevel,
        is_actionable: bool,
    ) -> TransitionDecision:
        curr = (current_status or "NOT_APPLIED").upper()
        if curr not in STATE_RANK:
            curr = "NOT_APPLIED"

        # 0. Ambiguous or Low Confidence Matches -> NEVER auto-mutate state
        if confidence_level in (ConfidenceLevel.AMBIGUOUS, ConfidenceLevel.LOW):
            return TransitionDecision(
                is_legal=False,
                should_mutate=False,
                current_status=curr,
                proposed_status=curr,
                event_status=EventStatus.PENDING_CONFIRMATION,
                reason=f"Event confidence is {confidence_level.value}; requires human confirmation.",
            )

        # 1. Non-actionable Event Types (Evidence only)
        # Amendment 2: ASSESSMENT_REQUEST is timeline evidence only
        if event_type == EventType.ASSESSMENT_REQUEST:
            return TransitionDecision(
                is_legal=True,
                should_mutate=False,
                current_status=curr,
                proposed_status=curr,
                event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                reason="ASSESSMENT_REQUEST is recorded as timeline evidence; application status remains unchanged.",
            )

        # Amendment 3: RECRUITER_CONTACT is timeline evidence only
        if event_type == EventType.RECRUITER_CONTACT:
            return TransitionDecision(
                is_legal=True,
                should_mutate=False,
                current_status=curr,
                proposed_status=curr,
                event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                reason="RECRUITER_CONTACT is recorded as timeline evidence; application status remains unchanged.",
            )

        if event_type in (EventType.INTERVIEW_UPDATE, EventType.APPLICATION_UPDATE, EventType.FOLLOW_UP, EventType.IRRELEVANT):
            return TransitionDecision(
                is_legal=True,
                should_mutate=False,
                current_status=curr,
                proposed_status=curr,
                event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                reason=f"{event_type.value} is informational evidence; application status remains unchanged.",
            )

        # 2. Actionable: APPLICATION_CONFIRMATION -> Target APPLIED
        if event_type == EventType.APPLICATION_CONFIRMATION:
            if curr in ("NOT_APPLIED", "READY_TO_APPLY", "RECRUITER_CONTACT"):
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=True,
                    current_status=curr,
                    proposed_status="APPLIED",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason=f"Legal forward transition: {curr} -> APPLIED from application confirmation.",
                )
            elif curr == "APPLIED":
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status="APPLIED",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason="Opportunity already marked APPLIED; event linked without mutation.",
                )
            else:
                # Anti-regression protection: INTERVIEW, OFFER, REJECTED cannot regress to APPLIED
                return TransitionDecision(
                    is_legal=False,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status=curr,
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason=f"Anti-regression safeguard: Cannot regress advanced status '{curr}' to 'APPLIED' from late confirmation email.",
                )

        # 3. Actionable: INTERVIEW_INVITATION -> Target INTERVIEW
        if event_type == EventType.INTERVIEW_INVITATION:
            if curr in ("NOT_APPLIED", "READY_TO_APPLY", "RECRUITER_CONTACT", "APPLIED"):
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=True,
                    current_status=curr,
                    proposed_status="INTERVIEW",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason=f"Legal forward transition: {curr} -> INTERVIEW from interview invitation.",
                )
            elif curr == "INTERVIEW":
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status="INTERVIEW",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason="Opportunity already marked INTERVIEW; event linked without mutation.",
                )
            else:
                # Anti-regression: OFFER cannot regress to INTERVIEW
                return TransitionDecision(
                    is_legal=False,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status=curr,
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason=f"Anti-regression safeguard: Cannot regress advanced status '{curr}' to 'INTERVIEW'.",
                )

        # 4. Actionable: OFFER -> Target OFFER
        if event_type == EventType.OFFER:
            if curr == "OFFER":
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status="OFFER",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason="Opportunity already marked OFFER; event linked without mutation.",
                )
            elif curr == "WITHDRAWN":
                return TransitionDecision(
                    is_legal=False,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status=curr,
                    event_status=EventStatus.PENDING_CONFIRMATION,
                    reason="Opportunity was WITHDRAWN; offer requires human confirmation.",
                )
            else:
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=True,
                    current_status=curr,
                    proposed_status="OFFER",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason=f"Legal forward transition: {curr} -> OFFER from formal offer letter.",
                )

        # 5. Actionable: REJECTION -> Target REJECTED
        if event_type == EventType.REJECTION:
            if curr == "OFFER":
                return TransitionDecision(
                    is_legal=False,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status=curr,
                    event_status=EventStatus.PENDING_CONFIRMATION,
                    reason="Opportunity is currently marked OFFER; rejection email requires human review.",
                )
            elif curr == "REJECTED":
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=False,
                    current_status=curr,
                    proposed_status="REJECTED",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason="Opportunity already marked REJECTED; event linked without mutation.",
                )
            else:
                return TransitionDecision(
                    is_legal=True,
                    should_mutate=True,
                    current_status=curr,
                    proposed_status="REJECTED",
                    event_status=EventStatus.AUTOMATIC_APPLIED if confidence_level == ConfidenceLevel.HIGH else EventStatus.PENDING_CONFIRMATION,
                    reason=f"Legal transition: {curr} -> REJECTED from rejection notice.",
                )

        return TransitionDecision(
            is_legal=False,
            should_mutate=False,
            current_status=curr,
            proposed_status=curr,
            event_status=EventStatus.PENDING_CONFIRMATION,
            reason="Unrecognized event type or transition path.",
        )
