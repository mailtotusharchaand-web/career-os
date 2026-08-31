"""
career_os.email — Provider-Agnostic Email Ingestion, Classification, Matching, and Lifecycle Layer.
"""

from .models import (
    RawEmailMessage,
    EmailClassification,
    OpportunityMatchResult,
    CareerEvent,
    EventType,
    ConfidenceLevel,
    EventStatus,
)
from .classifier import EmailClassifier
from .matcher import OpportunityMatcher
from .lifecycle import LifecycleValidator, TransitionDecision
from .token_store import TokenStore, LocalSecureFileTokenStore
from .oauth import GoogleOAuthClient, OAuthConfigurationError
from .sync_service import EmailSyncService, SyncReport, ProcessedEmailResult
from .dry_run_report import format_dry_run_report
from .adapters.base import BaseEmailAdapter
from .adapters.mock_adapter import MockEmailAdapter
from .adapters.gmail_adapter import GmailEmailAdapter

__all__ = [
    "RawEmailMessage",
    "EmailClassification",
    "OpportunityMatchResult",
    "CareerEvent",
    "EventType",
    "ConfidenceLevel",
    "EventStatus",
    "EmailClassifier",
    "OpportunityMatcher",
    "LifecycleValidator",
    "TransitionDecision",
    "TokenStore",
    "LocalSecureFileTokenStore",
    "GoogleOAuthClient",
    "OAuthConfigurationError",
    "EmailSyncService",
    "SyncReport",
    "ProcessedEmailResult",
    "format_dry_run_report",
    "BaseEmailAdapter",
    "MockEmailAdapter",
    "GmailEmailAdapter",
]
