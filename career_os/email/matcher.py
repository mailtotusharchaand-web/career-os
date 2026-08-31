"""
career_os.email.matcher — Multi-Signal Opportunity Matcher for Career OS.

Matches incoming email evidence against existing discovered opportunities in SQLite.
Enforces strict confidence tiers:
- HIGH: Exact requisition ID, exact job URL, or exact normalized company + role.
- MEDIUM: Exact company + fuzzy role similarity.
- AMBIGUOUS: Multiple candidate opportunities matched at the same company with similar scores.
- LOW: Weak domain signal or no match found (UNMATCHED_EMAIL).

Never duplicates or automatically inserts new opportunities.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from .models import (
    RawEmailMessage,
    EmailClassification,
    OpportunityMatchResult,
    ConfidenceLevel,
)


def _tokenize(text: str) -> set:
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return set(w for w in cleaned.split() if len(w) > 2)


def _jaccard_similarity(set1: set, set2: set) -> float:
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return float(intersection) / float(union) if union > 0 else 0.0


def _normalize_string(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"[^\w]", "", s.lower())


class OpportunityMatcher:
    """Matches email evidence against existing Career OS opportunities."""

    def __init__(self, opportunities: Optional[List[Dict[str, Any]]] = None):
        """
        Args:
            opportunities: List of opportunity dicts (from DB or workstation data).
        """
        self.opportunities = opportunities or []

    def set_opportunities(self, opportunities: List[Dict[str, Any]]) -> None:
        self.opportunities = opportunities

    def match(
        self,
        message: RawEmailMessage,
        classification: EmailClassification,
        previous_thread_opportunity_id: Optional[str] = None,
    ) -> OpportunityMatchResult:
        """
        Finds the best matching opportunity for an email.
        """
        # 1. Thread Continuity Match (if a previous message in the same thread matched an opportunity)
        if previous_thread_opportunity_id:
            for opp in self.opportunities:
                if opp.get("id") == previous_thread_opportunity_id:
                    return OpportunityMatchResult(
                        opportunity_id=opp["id"],
                        confidence_score=0.98,
                        confidence_level=ConfidenceLevel.HIGH,
                        match_signals=["thread_continuity_match"],
                        candidate_matches=[{"opportunity_id": opp["id"], "score": 0.98, "title": opp.get("title"), "company": opp.get("company")}],
                        reasoning=f"Matched existing conversation thread to opportunity {opp['id']} ('{opp.get('title')}' at '{opp.get('company')}').",
                    )

        if not self.opportunities:
            return OpportunityMatchResult(
                opportunity_id=None,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                match_signals=[],
                candidate_matches=[],
                reasoning="No opportunities in database to match against.",
            )

        extracted_req_id = classification.detected_requisition_id
        detected_company = classification.detected_company or ""
        detected_role = classification.detected_role or ""
        norm_detected_company = _normalize_string(detected_company)
        norm_detected_role = _normalize_string(detected_role)
        email_body = message.body_text or ""
        email_subject = message.subject or ""
        combined_email_text = f"{email_subject}\n{email_body}".lower()

        scored_candidates: List[Tuple[float, List[str], Dict[str, Any]]] = []

        for opp in self.opportunities:
            opp_id = opp.get("id")
            opp_title = opp.get("title", "")
            opp_company = opp.get("company", "")
            opp_norm_title = opp.get("normalized_title") or opp_title.lower().strip()
            opp_norm_comp = opp.get("normalized_company") or opp_company.lower().strip()
            opp_url = opp.get("job_url", "")
            opp_desc = opp.get("description", "")

            signals = []
            score = 0.0

            # Signal A: Exact Requisition / Reference ID match in Job Description or URL
            if extracted_req_id and (extracted_req_id.lower() in opp_desc.lower() or extracted_req_id.lower() in opp_url.lower()):
                signals.append("exact_requisition_id")
                score += 0.95

            # Signal B: Exact Job URL match in Email body
            if opp_url and len(opp_url) > 12 and opp_url.lower() in email_body.lower():
                signals.append("exact_job_url")
                score += 0.90

            # Signal C: Company matching
            company_matched = False
            norm_comp_clean = _normalize_string(opp_norm_comp)
            if norm_detected_company and norm_comp_clean and (
                norm_detected_company == norm_comp_clean or
                norm_detected_company in norm_comp_clean or
                norm_comp_clean in norm_detected_company
            ):
                company_matched = True
                signals.append("company_name_match")
            elif opp_company.lower() in combined_email_text:
                company_matched = True
                signals.append("company_text_mention")

            # Signal D: Title / Role matching
            title_score = 0.0
            if company_matched:
                if norm_detected_role and norm_detected_role == _normalize_string(opp_norm_title):
                    title_score = 0.50
                    signals.append("exact_role_match")
                else:
                    # Token overlap / Jaccard similarity between detected role & opportunity title
                    role_tokens = _tokenize(detected_role or email_subject)
                    opp_title_tokens = _tokenize(opp_title)
                    sim = _jaccard_similarity(role_tokens, opp_title_tokens)
                    if sim >= 0.5:
                        title_score = 0.40 * sim
                        signals.append(f"role_token_similarity_{sim:.2f}")
                    elif opp_title.lower() in combined_email_text:
                        title_score = 0.30
                        signals.append("role_title_text_mention")

                company_base_score = 0.45
                combined_score = company_base_score + title_score
                if combined_score > score:
                    score = min(0.95, combined_score)

            if score > 0.35:
                scored_candidates.append((score, signals, opp))

        # Sort candidates descending by score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        if not scored_candidates:
            return OpportunityMatchResult(
                opportunity_id=None,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                match_signals=[],
                candidate_matches=[],
                reasoning="No candidate opportunity matched company or role signals.",
            )

        top_score, top_signals, top_opp = scored_candidates[0]

        candidate_summaries = [
            {
                "opportunity_id": c[2].get("id"),
                "score": round(c[0], 3),
                "title": c[2].get("title"),
                "company": c[2].get("company"),
                "signals": c[1],
            }
            for c in scored_candidates[:5]
        ]

        # Check for Ambiguity (Multiple close candidates from the same company or identical scores)
        if len(scored_candidates) > 1:
            second_score = scored_candidates[1][0]
            # If top score is not overwhelmingly distinct (>0.15 margin) and < 0.90, mark AMBIGUOUS
            if (top_score - second_score < 0.12) and top_score < 0.90:
                return OpportunityMatchResult(
                    opportunity_id=None,  # Do not auto-bind ambiguous matches
                    confidence_score=round(top_score, 3),
                    confidence_level=ConfidenceLevel.AMBIGUOUS,
                    match_signals=top_signals,
                    candidate_matches=candidate_summaries,
                    reasoning=f"Ambiguous match across {len(candidate_summaries)} opportunities at similar confidence. Requires human confirmation.",
                )

        # High Confidence Match
        if top_score >= 0.80:
            return OpportunityMatchResult(
                opportunity_id=top_opp.get("id"),
                confidence_score=round(top_score, 3),
                confidence_level=ConfidenceLevel.HIGH,
                match_signals=top_signals,
                candidate_matches=candidate_summaries,
                reasoning=f"High-confidence match to {top_opp.get('id')} ('{top_opp.get('title')}' at '{top_opp.get('company')}').",
            )

        # Medium Confidence Match
        if top_score >= 0.55:
            return OpportunityMatchResult(
                opportunity_id=top_opp.get("id"),
                confidence_score=round(top_score, 3),
                confidence_level=ConfidenceLevel.MEDIUM,
                match_signals=top_signals,
                candidate_matches=candidate_summaries,
                reasoning=f"Medium-confidence match to {top_opp.get('id')} ('{top_opp.get('title')}' at '{top_opp.get('company')}').",
            )

        # Low Confidence Match -> Treat as Unmatched
        return OpportunityMatchResult(
            opportunity_id=None,
            confidence_score=round(top_score, 3),
            confidence_level=ConfidenceLevel.LOW,
            match_signals=top_signals,
            candidate_matches=candidate_summaries,
            reasoning=f"Low confidence ({top_score:.2f}); candidate match surfaced for review but not auto-bound.",
        )
