"""
career_os.email.dry_run_report — Formats SyncReport into Human-Readable Inspection Reports.
"""

from typing import Dict, Any, List
from .sync_service import SyncReport, ProcessedEmailResult


def format_dry_run_report(report: SyncReport) -> str:
    """Formats a SyncReport into a structured ASCII inspection report."""
    lines = []
    lines.append("=============================================================")
    lines.append("           CAREER OS — GMAIL SYNC PREVIEW (DRY RUN)          ")
    lines.append("=============================================================")
    lines.append(f"Account Email                    : {report.account_id}")
    lines.append(f"Provider                         : {report.provider}")
    lines.append(f"Started At                       : {report.started_at}")
    lines.append(f"Execution Mode                   : {'DRY RUN (NO MUTATION)' if report.dry_run else 'LIVE MUTATION'}")
    lines.append("-------------------------------------------------------------")
    lines.append(f"Messages Scanned                 : {report.total_messages_fetched}")
    lines.append(f"New Messages Inspected           : {report.new_messages_processed}")
    lines.append(f"Duplicate Messages Skipped       : {report.duplicate_messages_skipped}")
    lines.append("-------------------------------------------------------------")
    lines.append("CLASSIFICATION BREAKDOWN")

    counts_by_event: Dict[str, int] = {}
    for r in report.processed_results:
        counts_by_event[r.event_type] = counts_by_event.get(r.event_type, 0) + 1

    for ev_type, count in sorted(counts_by_event.items()):
        lines.append(f"  • {ev_type:<30}: {count}")

    lines.append("-------------------------------------------------------------")
    lines.append("MATCHING & ACTIONABILITY SUMMARY")
    lines.append(f"  • Matched to Career OS Jobs    : {len([r for r in report.processed_results if r.matched_opportunity_id])}")
    lines.append(f"  • Actionable State Transitions : {report.actionable_transitions_count}")
    lines.append(f"  • Evidence-Only Events         : {report.evidence_only_events_count}")
    lines.append(f"  • Ambiguous Matches (Pending)  : {report.ambiguous_matches_count}")
    lines.append(f"  • Unmatched Emails             : {report.unmatched_emails_count}")
    lines.append(f"  • Irrelevant / Spam / Alerts   : {report.irrelevant_emails_count}")
    lines.append("-------------------------------------------------------------")
    lines.append("PROPOSED STATE CHANGES & EVIDENCE DETAILS")

    if not report.processed_results:
        lines.append("  (No messages processed)")
    else:
        for idx, res in enumerate(report.processed_results, 1):
            lines.append(f"\n[{idx}] Message: '{res.subject}'")
            lines.append(f"    Sender     : {res.sender}")
            lines.append(f"    Event Type : {res.event_type} (Confidence: {res.confidence_level})")
            if res.matched_opportunity_id:
                lines.append(f"    Matched Job: {res.matched_opportunity_id}")
                if res.will_mutate_status:
                    lines.append(f"    Transition : {res.current_application_status} -> {res.proposed_application_status} (PROPOSED)")
                else:
                    lines.append(f"    Transition : NONE (Status remains {res.current_application_status})")
            else:
                lines.append(f"    Matched Job: NONE ({'AMBIGUOUS MATCH' if res.is_ambiguous else 'UNMATCHED'})")
            lines.append(f"    Reasoning  : {res.reasoning}")

    lines.append("\n=============================================================")
    if report.dry_run:
        lines.append("DRY RUN COMPLETE — ZERO DATABASE MUTATIONS APPLIED.")
    else:
        lines.append(f"LIVE SYNC COMPLETE — {report.mutations_applied} MUTATIONS PERSISTED IN SQLITE.")
    lines.append("=============================================================\n")
    return "\n".join(lines)
