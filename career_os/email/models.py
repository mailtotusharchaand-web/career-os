"""
career_os.email.models — Provider-agnostic domain models for email messages,
classifications, matching results, and career timeline events.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from typing import Dict, Any, List, Optional


class EventType(str, Enum):
    APPLICATION_CONFIRMATION = "APPLICATION_CONFIRMATION"
    RECRUITER_CONTACT = "RECRUITER_CONTACT"
    ASSESSMENT_REQUEST = "ASSESSMENT_REQUEST"
    INTERVIEW_INVITATION = "INTERVIEW_INVITATION"
    INTERVIEW_UPDATE = "INTERVIEW_UPDATE"
    REJECTION = "REJECTION"
    OFFER = "OFFER"
    APPLICATION_UPDATE = "APPLICATION_UPDATE"
    FOLLOW_UP = "FOLLOW_UP"
    IRRELEVANT = "IRRELEVANT"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    AMBIGUOUS = "AMBIGUOUS"


class EventStatus(str, Enum):
    AUTOMATIC_APPLIED = "AUTOMATIC_APPLIED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    IGNORED = "IGNORED"


@dataclass
class RawEmailMessage:
    provider: str  # e.g., 'gmail', 'mock', 'outlook'
    account_id: str  # e.g., 'user@gmail.com'
    message_id: str  # Provider's stable message ID
    thread_id: str  # Provider's stable thread ID
    sender: str  # Full sender string, e.g. "Recruiting <jobs@swiggy.in>"
    recipients: List[str]  # List of recipient email addresses
    subject: str
    body_text: str
    received_at: str  # ISO8601 UTC timestamp
    snippet: str = ""
    labels: List[str] = field(default_factory=list)
    headers: Dict[str, str] = field(default_factory=dict)
    attachments_metadata: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if not self.snippet and self.body_text:
            cleaned = " ".join(self.body_text.strip().split())
            self.snippet = cleaned[:240]

    @property
    def sender_email(self) -> str:
        """Extracts clean email address from sender string."""
        match = re.search(r"<([^>]+)>", self.sender)
        if match:
            return match.group(1).strip().lower()
        if "@" in self.sender:
            return self.sender.strip().lower()
        return self.sender.strip().lower()

    @property
    def sender_domain(self) -> str:
        """Extracts domain from sender email."""
        email = self.sender_email
        if "@" in email:
            return email.split("@")[-1].strip().lower()
        return ""

    @property
    def body_hash(self) -> str:
        """Deterministic hash of body text."""
        cleaned = " ".join(self.body_text.strip().split()).lower()
        return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawEmailMessage":
        return cls(
            provider=data.get("provider", "unknown"),
            account_id=data.get("account_id", ""),
            message_id=data.get("message_id", ""),
            thread_id=data.get("thread_id", ""),
            sender=data.get("sender", ""),
            recipients=data.get("recipients", []),
            subject=data.get("subject", ""),
            body_text=data.get("body_text", ""),
            received_at=data.get("received_at", datetime.now(timezone.utc).isoformat()),
            snippet=data.get("snippet", ""),
            labels=data.get("labels", []),
            headers=data.get("headers", {}),
            attachments_metadata=data.get("attachments_metadata", []),
        )


@dataclass
class EmailClassification:
    event_type: EventType
    confidence_score: float  # 0.0 to 1.0
    confidence_level: ConfidenceLevel
    is_actionable_state_transition: bool  # True for APPLICATION_CONFIRMATION, INTERVIEW_INVITATION, OFFER, REJECTION
    reasoning: str
    detected_company: Optional[str] = None
    detected_role: Optional[str] = None
    detected_requisition_id: Optional[str] = None
    extracted_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["confidence_level"] = self.confidence_level.value
        return d


@dataclass
class OpportunityMatchResult:
    opportunity_id: Optional[str]
    confidence_score: float  # 0.0 to 1.0
    confidence_level: ConfidenceLevel
    match_signals: List[str]  # e.g., ['exact_requisition_id', 'normalized_company_title']
    candidate_matches: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["confidence_level"] = self.confidence_level.value
        return d


@dataclass
class CareerEvent:
    id: str  # e.g., 'event_0001' or hash-based
    event_type: EventType
    opportunity_id: Optional[str]
    occurred_at: str  # ISO8601 UTC
    source_provider: str  # 'gmail', 'mock'
    source_account_id: str
    source_message_id: str
    source_thread_id: str
    confidence_score: float
    confidence_level: ConfidenceLevel
    status: EventStatus
    evidence: Dict[str, Any]
    candidate_matches: List[Dict[str, Any]] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        d["confidence_level"] = self.confidence_level.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareerEvent":
        return cls(
            id=data["id"],
            event_type=EventType(data["event_type"]),
            opportunity_id=data.get("opportunity_id"),
            occurred_at=data["occurred_at"],
            source_provider=data["source_provider"],
            source_account_id=data["source_account_id"],
            source_message_id=data["source_message_id"],
            source_thread_id=data.get("source_thread_id", ""),
            confidence_score=float(data.get("confidence_score", 0.0)),
            confidence_level=ConfidenceLevel(data.get("confidence_level", "MEDIUM")),
            status=EventStatus(data.get("status", "PENDING_CONFIRMATION")),
            evidence=data.get("evidence", {}),
            candidate_matches=data.get("candidate_matches", []),
            notes=data.get("notes"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )
