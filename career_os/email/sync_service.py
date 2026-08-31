"""
career_os.email.sync_service — Email Synchronization Engine with Dry-Run & Idempotency.

Orchestrates:
1. Fetching raw messages from an email adapter (Mock or Live Gmail).
2. Deduplication check via email_raw_messages.
3. Layered classification via EmailClassifier.
4. Deterministic multi-signal matching via OpportunityMatcher.
5. Lifecycle transition validation via LifecycleValidator.
6. Dry-run execution reporting (zero DB mutation) OR atomic transaction persistence.
7. Durable checkpoint advancement.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
from typing import List, Dict, Any, Optional

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
from .adapters.base import BaseEmailAdapter
from ..db.repository import CareerOSRepository


@dataclass
class ProcessedEmailResult:
    message_id: str
    subject: str
    sender: str
    received_at: str
    event_type: str
    confidence_level: str
    is_actionable: bool
    matched_opportunity_id: Optional[str]
    current_application_status: Optional[str]
    proposed_application_status: Optional[str]
    will_mutate_status: bool
    is_ambiguous: bool
    event_id: str
    reasoning: str


@dataclass
class SyncReport:
    provider: str
    account_id: str
    started_at: str
    completed_at: str
    dry_run: bool
    total_messages_fetched: int
    new_messages_processed: int
    duplicate_messages_skipped: int
    actionable_transitions_count: int
    evidence_only_events_count: int
    ambiguous_matches_count: int
    unmatched_emails_count: int
    irrelevant_emails_count: int
    mutations_applied: int
    processed_results: List[ProcessedEmailResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


class EmailSyncService:
    """Orchestrates email synchronization, classification, matching, and state persistence."""

    def __init__(
        self,
        adapter: BaseEmailAdapter,
        repository: CareerOSRepository,
        classifier: Optional[EmailClassifier] = None,
        matcher: Optional[OpportunityMatcher] = None,
    ):
        self.adapter = adapter
        self.repository = repository
        self.classifier = classifier or EmailClassifier()
        self.matcher = matcher or OpportunityMatcher()

    def run_sync(
        self,
        query: Optional[str] = None,
        max_results: int = 50,
        after_date: Optional[str] = None,
        dry_run: bool = False,
    ) -> SyncReport:
        started_at = datetime.now(timezone.utc).isoformat()
        account_id = self.adapter.get_account_email() or "unknown@example.com"
        provider = getattr(self.adapter, "provider_name", "mock")

        # 1. Fetch opportunities from repository to prime matcher
        workstation_data = self.repository.get_workstation_data()
        opportunities = workstation_data.get("jobs", [])
        self.matcher.set_opportunities(opportunities)

        # 2. Fetch messages from adapter
        messages = self.adapter.fetch_messages(query=query, max_results=max_results, after_date=after_date)

        report = SyncReport(
            provider=provider,
            account_id=account_id,
            started_at=started_at,
            completed_at="",
            dry_run=dry_run,
            total_messages_fetched=len(messages),
            new_messages_processed=0,
            duplicate_messages_skipped=0,
            actionable_transitions_count=0,
            evidence_only_events_count=0,
            ambiguous_matches_count=0,
            unmatched_emails_count=0,
            irrelevant_emails_count=0,
            mutations_applied=0,
            processed_results=[],
        )

        newest_timestamp = None

        for msg in messages:
            msg_id = msg.message_id
            if not newest_timestamp or msg.received_at > newest_timestamp:
                newest_timestamp = msg.received_at

            # Check Idempotency / Deduplication
            if self.repository.is_raw_email_processed(provider, account_id, msg_id):
                report.duplicate_messages_skipped += 1
                continue

            report.new_messages_processed += 1

            # 3. Layered Classification
            classification = self.classifier.classify(msg)

            # 4. Opportunity Matching
            match_result = self.matcher.match(msg, classification)
            opp_id = match_result.opportunity_id

            # Lookup current opportunity status
            current_app_status = "NOT_APPLIED"
            if opp_id:
                opp_obj = self.repository.get_opportunity_by_id(opp_id)
                if opp_obj:
                    current_app_status = opp_obj.get("current_application_status", "NOT_APPLIED")

            # 5. Lifecycle Transition Validation
            decision = LifecycleValidator.evaluate_transition(
                current_status=current_app_status,
                event_type=classification.event_type,
                confidence_level=match_result.confidence_level,
                is_actionable=classification.is_actionable_state_transition,
            )

            # Track statistics
            if classification.event_type == EventType.IRRELEVANT:
                report.irrelevant_emails_count += 1
            elif match_result.confidence_level == ConfidenceLevel.AMBIGUOUS:
                report.ambiguous_matches_count += 1
            elif opp_id is None:
                report.unmatched_emails_count += 1
            elif decision.should_mutate:
                report.actionable_transitions_count += 1
            else:
                report.evidence_only_events_count += 1

            # Build CareerEvent ID
            event_id = f"evt_{hashlib.sha256(f'{provider}_{account_id}_{msg_id}'.encode('utf-8')).hexdigest()[:16]}"

            res_item = ProcessedEmailResult(
                message_id=msg_id,
                subject=msg.subject,
                sender=msg.sender,
                received_at=msg.received_at,
                event_type=classification.event_type.value,
                confidence_level=match_result.confidence_level.value,
                is_actionable=classification.is_actionable_state_transition,
                matched_opportunity_id=opp_id,
                current_application_status=current_app_status if opp_id else None,
                proposed_application_status=decision.proposed_status if opp_id else None,
                will_mutate_status=decision.should_mutate,
                is_ambiguous=(match_result.confidence_level == ConfidenceLevel.AMBIGUOUS),
                event_id=event_id,
                reasoning=decision.reason,
            )
            report.processed_results.append(res_item)

            # 6. Persistence (Only if not dry_run)
            if not dry_run:
                event_data = {
                    "id": event_id,
                    "event_type": classification.event_type.value,
                    "opportunity_id": opp_id,
                    "occurred_at": msg.received_at,
                    "source_provider": provider,
                    "source_account_id": account_id,
                    "source_message_id": msg_id,
                    "source_thread_id": msg.thread_id,
                    "confidence_score": match_result.confidence_score,
                    "confidence_level": match_result.confidence_level.value,
                    "status": decision.event_status.value,
                    "evidence": {
                        "subject": msg.subject,
                        "sender": msg.sender,
                        "snippet": msg.snippet,
                        "reasoning": classification.reasoning,
                        "detected_company": classification.detected_company,
                        "detected_role": classification.detected_role,
                        "match_signals": match_result.match_signals,
                    },
                    "candidate_matches": match_result.candidate_matches,
                    "notes": decision.reason,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }

                raw_msg_data = {
                    "provider": provider,
                    "account_id": account_id,
                    "message_id": msg_id,
                    "thread_id": msg.thread_id,
                    "sender": msg.sender,
                    "sender_domain": msg.sender_domain,
                    "recipients": msg.recipients,
                    "subject": msg.subject,
                    "snippet": msg.snippet,
                    "body_hash": msg.body_hash,
                    "received_at": msg.received_at,
                    "labels": msg.labels,
                }

                _, did_mutate = self.repository.record_career_event_and_transition(
                    event_data=event_data,
                    raw_message_data=raw_msg_data,
                    should_mutate_status=decision.should_mutate,
                    new_application_status=decision.proposed_status,
                    transition_notes=decision.reason,
                )
                if did_mutate:
                    report.mutations_applied += 1

        completed_at = datetime.now(timezone.utc).isoformat()
        report.completed_at = completed_at

        # 7. Advance checkpoint (Only on live run after all messages processed)
        if not dry_run:
            self.repository.update_email_sync_checkpoint(
                provider=provider,
                account_id=account_id,
                last_synced_at=completed_at,
                last_message_timestamp=newest_timestamp,
                sync_status="HEALTHY",
                messages_increment=report.new_messages_processed,
            )

        return report
