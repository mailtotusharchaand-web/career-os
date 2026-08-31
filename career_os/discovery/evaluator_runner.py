"""
career_os/discovery/evaluator_runner.py — Resumable, transactional evaluation execution engine.
Evaluates PENDING opportunities in SQLite using candidate CV and LLM with deterministic reuse checks.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from career_os.db.repository import CareerOSRepository, compute_content_hash
from evaluate import (
    _llm_config,
    build_prompt,
    call_llm,
    extract_json,
    parse_cv,
    run_explicit_constraint_gates,
    validate_evaluation,
)

log = logging.getLogger("evaluator_runner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class EvaluationRunner:
    """
    Transactional runner that evaluates PENDING opportunities in SQLite.
    Features:
    - Deterministic evaluation reuse checks before LLM invocation
    - Candidate constraint gate filtering (0 token cost for explicit exclusions)
    - Structured validation of LLM outputs
    - Atomic per-opportunity persistence
    - Full resumability and failure isolation
    - Observable accounting metrics
    """

    def __init__(
        self,
        db_path: str = "career_os.db",
        cv_path: str = "Tushar_Chaand_CV.docx",
        llm_caller: Optional[Callable[[str, dict], str]] = None,
        inter_call_delay: float = 1.0,
    ):
        self.db_path = db_path
        self.cv_path = cv_path
        self.repo = CareerOSRepository(db_path=db_path)
        self.llm_caller = llm_caller or call_llm
        self.inter_call_delay = inter_call_delay
        self._cv_text: Optional[str] = None
        self._llm_cfg: Optional[dict] = None

    def get_cv_text(self) -> str:
        if self._cv_text is None:
            self._cv_text = parse_cv(self.cv_path)
        return self._cv_text

    def get_llm_config(self) -> dict:
        if self._llm_cfg is None:
            self._llm_cfg = _llm_config()
        return self._llm_cfg

    def get_pending_opportunities(self) -> List[Dict[str, Any]]:
        """Fetch all opportunities with evaluation_status = 'PENDING'."""
        with self.repo.connection() as conn:
            cur = conn.execute(
                """
                SELECT o.*, e.evaluation_status
                FROM opportunities o
                LEFT JOIN evaluations e ON o.id = e.opportunity_id
                WHERE e.evaluation_status = 'PENDING' OR e.evaluation_status IS NULL
                ORDER BY o.id ASC;
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def run(self, max_items: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute evaluation cycle on pending queue.
        Returns accounting metrics dictionary.
        """
        pending_queue = self.get_pending_opportunities()
        if max_items:
            pending_queue = pending_queue[:max_items]

        start_time = time.time()
        metrics = {
            "pending_at_start": len(pending_queue),
            "reused_during_run": 0,
            "fresh_evaluations_attempted": 0,
            "fresh_evaluations_succeeded": 0,
            "evaluations_failed": 0,
            "llm_calls_made": 0,
            "llm_calls_avoided": 0,
            "gate_rejected": 0,
            "remaining_pending": 0,
            "duration_seconds": 0.0,
        }

        log.info(f"Starting evaluation runner for {len(pending_queue)} pending opportunities.")

        for idx, opp in enumerate(pending_queue, 1):
            opp_id = opp["id"]
            title = opp.get("title", "")
            company = opp.get("company", "")
            log.info(f"[{idx}/{len(pending_queue)}] Processing {opp_id}: '{title}' @ '{company}'")

            # Step 1: Final Evaluation Reuse Check
            reused = self.repo.find_reusable_evaluation(opp)
            if reused:
                source_eval, reuse_type, reuse_reason = reused
                log.info(f"  -> Reusing evaluation ({reuse_type}) from {source_eval['id']}")
                self._persist_reused_evaluation(opp_id, source_eval, reuse_type, reuse_reason)
                metrics["reused_during_run"] += 1
                metrics["llm_calls_avoided"] += 1
                continue

            # Step 2: Explicit Candidate Constraint Gates
            gates_passed, passed_checks, failed_checks = run_explicit_constraint_gates(opp)
            if not gates_passed:
                log.info(f"  -> Gate rejected: {failed_checks}")
                self._persist_gate_failed_evaluation(opp_id, opp, passed_checks, failed_checks)
                metrics["gate_rejected"] += 1
                metrics["fresh_evaluations_succeeded"] += 1
                continue

            # Step 3: Fresh LLM Evaluation
            metrics["fresh_evaluations_attempted"] += 1
            success = self._evaluate_single_opportunity(opp, passed_checks, failed_checks, metrics)
            if success:
                metrics["fresh_evaluations_succeeded"] += 1
            else:
                metrics["evaluations_failed"] += 1

            # Inter-call rate limiting pause
            if self.inter_call_delay > 0 and idx < len(pending_queue):
                time.sleep(self.inter_call_delay)

        metrics["remaining_pending"] = len(self.get_pending_opportunities())
        metrics["duration_seconds"] = round(time.time() - start_time, 2)

        log.info("\n" + "=" * 60)
        log.info("EVALUATION RUN COMPLETE")
        log.info("-" * 60)
        for k, v in metrics.items():
            log.info(f"  {k:<30}: {v}")
        log.info("=" * 60)

        return metrics

    def evaluate_single_opportunity_by_id(self, opp_id: str) -> bool:
        """
        Explicitly evaluates a single opportunity by ID (useful for corrective evaluations).
        Runs explicit constraint gates, calls LLM, validates, and persists.
        """
        opp = self.repo.get_opportunity_by_id(opp_id)
        if not opp:
            log.error(f"Opportunity {opp_id} not found.")
            return False

        gates_passed, passed_checks, failed_checks = run_explicit_constraint_gates(opp)
        if not gates_passed:
            log.info(f"Gate rejected {opp_id}: {failed_checks}")
            self._persist_gate_failed_evaluation(opp_id, opp, passed_checks, failed_checks)
            return False

        dummy_metrics = {"llm_calls_made": 0}
        return self._evaluate_single_opportunity(opp, passed_checks, failed_checks, dummy_metrics)

    def _persist_reused_evaluation(
        self,
        opp_id: str,
        source_eval: Dict[str, Any],
        reuse_type: str,
        reuse_reason: str,
    ) -> None:
        """Atomically persist reused evaluation referencing source evaluation."""
        self.repo.insert_evaluation({
            "opportunity_id": opp_id,
            "recommendation": source_eval.get("recommendation"),
            "score": source_eval.get("score"),
            "fit_dimensions": source_eval.get("fit_dimensions", {}),
            "strengths": source_eval.get("strengths", []),
            "gaps": source_eval.get("gaps", []),
            "reasoning": source_eval.get("reasoning", ""),
            "gate_failed": source_eval.get("gate_failed", 0),
            "gate_failure_reasons": source_eval.get("gate_failure_reasons", []),
            "gate_passed_checks": source_eval.get("gate_passed_checks", []),
            "evaluated_at": source_eval.get("evaluated_at") or datetime.now(timezone.utc).isoformat(),
            "evaluator_model": source_eval.get("evaluator_model", "gemini-flash-lite-latest"),
            "content_hash": source_eval.get("content_hash", ""),
            "is_reused": 1,
            "reuse_type": reuse_type,
            "source_evaluation_id": source_eval["id"],
            "reuse_reason": reuse_reason,
            "evaluation_status": "REUSED",
        })

    def _persist_gate_failed_evaluation(
        self,
        opp_id: str,
        opp: Dict[str, Any],
        passed_checks: List[str],
        failed_checks: List[str],
    ) -> None:
        """Atomically persist gate-failed evaluation (0 LLM call)."""
        now = datetime.now(timezone.utc).isoformat()
        self.repo.insert_evaluation({
            "opportunity_id": opp_id,
            "recommendation": "Skip",
            "score": 0.0,
            "fit_dimensions": {},
            "strengths": [],
            "gaps": failed_checks,
            "reasoning": "Opportunity excluded by candidate constraint gate.",
            "gate_failed": 1,
            "gate_failure_reasons": failed_checks,
            "gate_passed_checks": passed_checks,
            "evaluated_at": now,
            "evaluator_model": "heuristic_gate",
            "content_hash": compute_content_hash(opp.get("description", "")),
            "is_reused": 0,
            "reuse_type": None,
            "source_evaluation_id": None,
            "reuse_reason": None,
            "evaluation_status": "EVALUATED",
        })

    def _evaluate_single_opportunity(
        self,
        opp: Dict[str, Any],
        passed_checks: List[str],
        failed_checks: List[str],
        metrics: Dict[str, Any],
    ) -> bool:
        """Call LLM, validate response structure, and persist atomically."""
        opp_id = opp["id"]
        cv_text = self.get_cv_text()
        llm_cfg = self.get_llm_config()
        prompt = build_prompt(cv_text, opp)

        try:
            metrics["llm_calls_made"] += 1
            raw_response = self.llm_caller(prompt, llm_cfg)
            parsed_json = extract_json(raw_response)
            validated = validate_evaluation(parsed_json)

            # Strict Structural Validation
            required_keys = ["overall_score", "role_fit", "recommendation", "reasoning"]
            for req in required_keys:
                if req not in validated or validated[req] is None:
                    raise ValueError(f"Missing required field '{req}' in LLM evaluation")

            fit_dims = {
                "role_fit": validated.get("role_fit"),
                "experience_fit": validated.get("current_experience_fit"),
                "transferable": validated.get("transferable_capability_fit"),
                "seniority_fit": validated.get("seniority_fit"),
                "opportunity_alignment": validated.get("opportunity_alignment"),
                "probability_of_obtaining": validated.get("probability_of_obtaining"),
                "transition_difficulty": validated.get("transition_difficulty"),
                "career_upside": validated.get("career_upside"),
                "compensation_upside": validated.get("compensation_upside"),
                "confidence": validated.get("confidence"),
                "evidence": validated.get("evidence"),
                "missing_evidence": validated.get("missing_evidence"),
            }

            now = datetime.now(timezone.utc).isoformat()
            self.repo.insert_evaluation({
                "opportunity_id": opp_id,
                "recommendation": validated.get("recommendation"),
                "score": float(validated.get("overall_score", 0)),
                "fit_dimensions": fit_dims,
                "strengths": validated.get("key_strengths", []),
                "gaps": validated.get("missing_critical_skills", []),
                "reasoning": validated.get("reasoning", ""),
                "gate_failed": 0,
                "gate_failure_reasons": failed_checks,
                "gate_passed_checks": passed_checks,
                "evaluated_at": now,
                "evaluator_model": llm_cfg.get("model", "gemini-flash-lite-latest"),
                "content_hash": compute_content_hash(opp.get("description", "")),
                "is_reused": 0,
                "reuse_type": None,
                "source_evaluation_id": None,
                "reuse_reason": None,
                "evaluation_status": "EVALUATED",
            })
            log.info(f"  -> Successfully evaluated: score={validated.get('overall_score')}, rec={validated.get('recommendation')}")
            return True

        except Exception as e:
            log.error(f"  -> Evaluation failed for {opp_id}: {e}")
            self._mark_evaluation_failed(opp_id, str(e))
            return False

    def _mark_evaluation_failed(self, opp_id: str, error_reason: str) -> None:
        """Mark evaluation status as FAILED with error reason."""
        now = datetime.now(timezone.utc).isoformat()
        with self.repo.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluations (
                    id, opportunity_id, recommendation, score, fit_dimensions_json,
                    strengths_json, gaps_json, reasoning, gate_failed, gate_failure_reasons_json,
                    gate_passed_checks_json, evaluated_at, evaluator_model, content_hash,
                    is_reused, reuse_type, source_evaluation_id, reuse_reason, evaluation_status
                ) VALUES (?, ?, 'FAILED', NULL, '{}', '[]', '[]', ?, 0, '[]', '[]', ?, 'system', '', 0, NULL, NULL, NULL, 'FAILED');
                """,
                (
                    f"eval_{opp_id}",
                    opp_id,
                    f"Evaluation execution failed: {error_reason[:300]}",
                    now,
                ),
            )
