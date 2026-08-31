"""
career_os.email.classifier — Layered Email Classifier for Career OS.

Uses high-precision deterministic signal matching first (known ATS domains,
recruiting keywords, structured subject lines, body regex patterns).
Ambiguous messages can optionally fall back to heuristic/LLM interpretation.

Enforces strict domain boundaries:
- APPLICATION_CONFIRMATION, INTERVIEW_INVITATION, OFFER, REJECTION are marked actionable.
- RECRUITER_CONTACT, ASSESSMENT_REQUEST, APPLICATION_UPDATE, FOLLOW_UP are timeline evidence only.
- IRRELEVANT messages do not affect application state.
"""

import re
from typing import Optional, Dict, Any, List
from .models import (
    RawEmailMessage,
    EmailClassification,
    EventType,
    ConfidenceLevel,
)

# Known ATS & Recruiting Domains
ATS_DOMAINS = {
    "greenhouse.io", "ghpostings.com", "lever.co", "hire.lever.co",
    "myworkday.com", "myworkdayjobs.com", "ashbyhq.com", "jobs.ashbyhq.com",
    "smartrecruiters.com", "icims.com", "taleo.net", "workable.com",
    "bamboohr.com", "rippling.com", "jobvite.com", "darwinbox.in",
    "keka.com", "freshteam.com", "recruitee.com", "pinpointhq.com",
}

# Negative / Irrelevant Signals (Job boards spam, generic newsletters, billing)
IRRELEVANT_PATTERNS = [
    r"\b\d+\s+new jobs?\b",
    r"\bjobs? recommended for you\b",
    r"\bjob alerts?\b",
    r"\bdaily job digest\b",
    r"\bweekly digest\b",
    r"\bunsubscribe\b.*\bjob recommendations\b",
    r"\bsecurity code\b",
    r"\bone[- ]time password\b",
    r"\botp\b",
    r"\bverification code\b",
    r"\border confirmation\b",
    r"\binvoice\b",
    r"\bpayment receipt\b",
    r"\byour subscription\b",
]

# Actionable Application Confirmation Patterns
APP_CONFIRM_PATTERNS = [
    r"\bthank you for applying\b",
    r"\bthanks for applying\b",
    r"\bwe(?:'ve| have) received your application\b",
    r"\byour application (?:has been|was) received\b",
    r"\byour application for .* (?:has been received|is confirmed)\b",
    r"\bapplication confirmation\b",
    r"\bapplication submitted successfully\b",
    r"\bwe appreciate your interest in\b",
    r"\bapplication acknowledgement\b",
]

# Actionable Interview Invitation Patterns
INTERVIEW_INVITATION_PATTERNS = [
    r"\binvitation to interview\b",
    r"\binterview invitation\b",
    r"\blike to invite you (?:to|for) an? interview\b",
    r"\bwould like to schedule an? interview\b",
    r"\bschedule your (?:technical |first round |next |final )?interview\b",
    r"\bchoose a time for your interview\b",
    r"\binterview with .* (?:team|lead|manager)\b",
    r"\bmeet the team\b",
    r"\bround \d+ interview\b",
]

# Interview Update / Reschedule Patterns
INTERVIEW_UPDATE_PATTERNS = [
    r"\binterview (?:rescheduled|confirmed|updated|reminder)\b",
    r"\breschedule your interview\b",
    r"\bdetails for your upcoming interview\b",
]

# Assessment Request Patterns (Evidence only - Amendment 2)
ASSESSMENT_PATTERNS = [
    r"\bonline assessment\b",
    r"\btake[- ]home (?:assessment|assignment|test|challenge)\b",
    r"\bhackerrank\b",
    r"\bcodility\b",
    r"\bcoding challenge\b",
    r"\btechnical assessment\b",
    r"\bcomplete the assessment\b",
    r"\btest invitation\b",
]

# Actionable Offer Patterns
OFFER_PATTERNS = [
    r"\boffer of employment\b",
    r"\bpleased to offer you the position\b",
    r"\bdelighted to offer you\b",
    r"\bofficial offer letter\b",
    r"\bjob offer\b",
    r"\bwelcome to the team\b",
]

# Actionable Rejection Patterns
REJECTION_PATTERNS = [
    r"\bunfortunately,?\s+(?:we\s+)?(?:will not|are not able to|cannot|are unable to)\s+(?:be\s+)?(?:moving|move)\s+forward\b",
    r"\bdecided to (?:pursue|move forward with)\s+other candidates\b",
    r"\bwe have decided not to move forward\b",
    r"\bafter careful consideration\b",
    r"\bnot\s+(?:been\s+)?selected for (?:this|the)\s+(?:role|position)\b",
    r"\bwe will not be proceeding with your application\b",
    r"\bwill not be moving forward with your application\b",
    r"\bwe will keep your (?:resume|profile)\s+on file\b",
    r"\bunfortunately,?\s+on this occasion\b",
    r"\bunable to offer you\b",
]

# Recruiter Outreach Patterns (Evidence only - Amendment 3)
RECRUITER_CONTACT_PATTERNS = [
    r"\bcame across your (?:profile|experience|background|linkedin)\b",
    r"\bimpressed by your (?:background|profile|experience)\b",
    r"\bexploring (?:new\s+)?opportunities\b",
    r"\bquick chat about a(?:n)?\s+(?:open|exciting)?\s+role\b",
    r"\bwould love to connect regarding\b",
    r"\bwe are looking for a .* and thought of you\b",
    r"\bopen to a conversation\b",
]


class EmailClassifier:
    """Deterministic layered classifier with explicit domain actionability rules."""

    def classify(self, message: RawEmailMessage) -> EmailClassification:
        subject = message.subject or ""
        body = message.body_text or ""
        sender = message.sender or ""
        combined_text = f"{subject}\n{body}".lower()
        sender_domain = message.sender_domain

        # 0. Check Irrelevant / Spam / Alert patterns
        if any(re.search(p, combined_text, re.IGNORECASE) for p in IRRELEVANT_PATTERNS):
            # Only treat as irrelevant if it does NOT match explicit confirmation/interview
            if not any(re.search(p, subject, re.IGNORECASE) for p in APP_CONFIRM_PATTERNS + INTERVIEW_INVITATION_PATTERNS):
                return EmailClassification(
                    event_type=EventType.IRRELEVANT,
                    confidence_score=0.95,
                    confidence_level=ConfidenceLevel.HIGH,
                    is_actionable_state_transition=False,
                    reasoning="Matched job alert, newsletter, OTP or transactional non-application pattern.",
                )

        extracted_metadata = self._extract_metadata(subject, body, sender, message.headers)
        detected_company = extracted_metadata.get("company")
        detected_role = extracted_metadata.get("role")
        detected_req_id = extracted_metadata.get("requisition_id")

        # 1. Offer Detection (Highest priority lifecycle signal)
        if any(re.search(p, combined_text, re.IGNORECASE) for p in OFFER_PATTERNS):
            return EmailClassification(
                event_type=EventType.OFFER,
                confidence_score=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                is_actionable_state_transition=True,
                reasoning="Explicit employment offer letter or offer statement detected.",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 2. Rejection Detection
        if any(re.search(p, combined_text, re.IGNORECASE) for p in REJECTION_PATTERNS):
            return EmailClassification(
                event_type=EventType.REJECTION,
                confidence_score=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                is_actionable_state_transition=True,
                reasoning="Explicit non-selection or application rejection statement detected.",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 3. Interview Invitation Detection
        if any(re.search(p, combined_text, re.IGNORECASE) for p in INTERVIEW_INVITATION_PATTERNS):
            return EmailClassification(
                event_type=EventType.INTERVIEW_INVITATION,
                confidence_score=0.92,
                confidence_level=ConfidenceLevel.HIGH,
                is_actionable_state_transition=True,
                reasoning="Interview scheduling or round invitation statement detected.",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 4. Interview Update / Reschedule Detection
        if any(re.search(p, combined_text, re.IGNORECASE) for p in INTERVIEW_UPDATE_PATTERNS):
            return EmailClassification(
                event_type=EventType.INTERVIEW_UPDATE,
                confidence_score=0.88,
                confidence_level=ConfidenceLevel.HIGH,
                is_actionable_state_transition=False,  # Evidence only
                reasoning="Interview update, reminder, or reschedule notice detected.",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 5. Assessment Request Detection (Evidence only - Amendment 2)
        if any(re.search(p, combined_text, re.IGNORECASE) for p in ASSESSMENT_PATTERNS):
            return EmailClassification(
                event_type=EventType.ASSESSMENT_REQUEST,
                confidence_score=0.90,
                confidence_level=ConfidenceLevel.HIGH,
                is_actionable_state_transition=False,  # Retained as CareerEvent evidence only
                reasoning="Assessment, take-home challenge, or coding test invitation detected (timeline evidence only).",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 6. Application Confirmation Detection
        if any(re.search(p, combined_text, re.IGNORECASE) for p in APP_CONFIRM_PATTERNS):
            return EmailClassification(
                event_type=EventType.APPLICATION_CONFIRMATION,
                confidence_score=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                is_actionable_state_transition=True,
                reasoning="Explicit application confirmation or submission acknowledgment detected.",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 7. Recruiter Outreach Detection (Evidence only - Amendment 3)
        if any(re.search(p, combined_text, re.IGNORECASE) for p in RECRUITER_CONTACT_PATTERNS):
            return EmailClassification(
                event_type=EventType.RECRUITER_CONTACT,
                confidence_score=0.85,
                confidence_level=ConfidenceLevel.MEDIUM,
                is_actionable_state_transition=False,  # Timeline evidence only
                reasoning="Recruiter inbound outreach detected (not an applied submission).",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 8. ATS Domain check fallback (if from ATS but no strong match)
        if sender_domain in ATS_DOMAINS:
            return EmailClassification(
                event_type=EventType.APPLICATION_UPDATE,
                confidence_score=0.70,
                confidence_level=ConfidenceLevel.MEDIUM,
                is_actionable_state_transition=False,
                reasoning=f"Received from known ATS platform ({sender_domain}); general application update.",
                detected_company=detected_company,
                detected_role=detected_role,
                detected_requisition_id=detected_req_id,
                extracted_metadata=extracted_metadata,
            )

        # 9. Default: Irrelevant / Non-actionable
        return EmailClassification(
            event_type=EventType.IRRELEVANT,
            confidence_score=0.80,
            confidence_level=ConfidenceLevel.MEDIUM,
            is_actionable_state_transition=False,
            reasoning="No recruiting, interview, confirmation, or rejection signals found.",
        )

    def _extract_metadata(self, subject: str, body: str, sender: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Extracts candidate company name, role title, and requisition ID from headers & text."""
        metadata: Dict[str, Any] = {}

        # 1. Requisition / Reference ID extraction
        req_match = re.search(r"\b(?:req(?:uisition)?|job|ref(?:erence)?|id)[\s#:_-]*([A-Z0-9_-]{4,16})\b", f"{subject}\n{body}", re.IGNORECASE)
        if req_match:
            metadata["requisition_id"] = req_match.group(1).strip()

        # 2. Company extraction from subject or sender
        # e.g., "Application to Swiggy", "Your application at Razorpay", "Flipkart Recruiting"
        comp_match = re.search(r"\b(?:at|to|with|from|@)\s+([A-Za-z0-9&.\s]{2,30}?)(?:\s+for|\s+team|\s+careers|[!:,]|$)", subject, re.IGNORECASE)
        if comp_match:
            metadata["company"] = comp_match.group(1).strip()
        else:
            # Try sender name
            sender_name_match = re.match(r"^([^<]+)", sender)
            if sender_name_match:
                name = sender_name_match.group(1).strip().replace('"', '')
                cleaned_name = re.sub(r"\b(?:Careers|Recruiting|Talent|HR|Jobs|Team|Hiring)\b", "", name, flags=re.IGNORECASE).strip()
                if cleaned_name and len(cleaned_name) > 1:
                    metadata["company"] = cleaned_name

        # 3. Role extraction from subject
        # e.g., "Application for Product Manager", "Interview: Staff Engineer - Platform"
        role_match = re.search(r"\b(?:for|position of|role of|interview:)\s+([A-Za-z0-9/,\-\s]{3,40}?)(?:\s+at|\s+with|\s+-\s+|[!:,]|$)", subject, re.IGNORECASE)
        if role_match:
            metadata["role"] = role_match.group(1).strip()

        return metadata
