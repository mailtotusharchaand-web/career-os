"""
career_os.db.migrate_json_to_sqlite — Self-contained migration & reconciliation script.
Imports historical Run 001 JSON datasets into career_os.db with full dynamic reconciliation.
"""

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from career_os.db.repository import CareerOSRepository, compute_canonical_key, compute_content_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("migration")

RESULTS_FILE = Path("india_discovery_results.json")
EVALS_FILE = Path("india_discovery_llm_evaluations.json")
REVIEWS_FILE = Path("discovery_human_review.json")
EXPECTED_RESULTS_SHA256 = "cb9b50c07601b7e7522e6d95555529531f4d95c8afa1792e0af847b593c8d786"
EXPECTED_EVALS_SHA256 = "885fe1a37dbd4151b826449a6dd4c56058a410c7c224154240c16a06f441983e"


def sha256_file(path: Path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_migration(db_path: str = "career_os.db") -> Tuple[bool, Dict[str, Any]]:
    log.info("=" * 65)
    log.info("CAREER OS — HISTORICAL DATA MIGRATION (RUN 001)")
    log.info("=" * 65)

    # 1. Verify JSON file presence & baseline hashes
    if not RESULTS_FILE.exists():
        raise FileNotFoundError(f"Missing required historical results file: {RESULTS_FILE}")
    if not EVALS_FILE.exists():
        raise FileNotFoundError(f"Missing required historical evaluations file: {EVALS_FILE}")

    res_hash = sha256_file(RESULTS_FILE)
    eval_hash = sha256_file(EVALS_FILE)

    log.info(f"Checking {RESULTS_FILE} SHA256: {res_hash}")
    log.info(f"Checking {EVALS_FILE} SHA256: {eval_hash}")

    if res_hash != EXPECTED_RESULTS_SHA256:
        raise ValueError(f"Hash mismatch for {RESULTS_FILE}! Expected {EXPECTED_RESULTS_SHA256}, got {res_hash}")
    if eval_hash != EXPECTED_EVALS_SHA256:
        raise ValueError(f"Hash mismatch for {EVALS_FILE}! Expected {EXPECTED_EVALS_SHA256}, got {eval_hash}")

    log.info("Baseline immutable file hashes strictly verified.")

    # 2. Dynamically load source JSON datasets
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results_data = json.load(f)
    results_list = results_data.get("results", [])
    total_json_opps = len(results_list)

    with open(EVALS_FILE, "r", encoding="utf-8") as f:
        evals_data = json.load(f)
    evals_list = evals_data.get("evaluations", []) if isinstance(evals_data, dict) else evals_data
    total_json_evals = len(evals_list)

    reviews_dict = {}
    if REVIEWS_FILE.exists():
        with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
            rev_raw = json.load(f)
            reviews_dict = rev_raw.get("decisions", {}) if isinstance(rev_raw, dict) else rev_raw
    total_json_reviews = len(reviews_dict)

    log.info(f"Dynamically loaded JSON sources: {total_json_opps} opportunities, {total_json_evals} evaluations, {total_json_reviews} human reviews.")

    # 3. Initialize repository
    repo = CareerOSRepository(db_path=db_path)
    repo.init_db()

    # 4. Perform atomic migration
    with repo.connection() as conn:
        # Clean existing tables in proper foreign key dependency order for idempotence
        conn.execute("DELETE FROM application_status_history;")
        conn.execute("DELETE FROM human_reviews;")
        conn.execute("DELETE FROM evaluations;")
        conn.execute("DELETE FROM discovery_run_opportunities;")
        conn.execute("DELETE FROM opportunity_sources;")
        conn.execute("DELETE FROM opportunities;")
        conn.execute("DELETE FROM discovery_runs;")

        # A. Insert Run 001
        run_id = "run_0001"
        conn.execute(
            """
            INSERT INTO discovery_runs (
                id, run_number, started_at, completed_at, status, cv_path, max_budget,
                total_raw_records, total_unique_opportunities, new_opportunities,
                previously_seen_opportunities, reappeared_opportunities, expired_opportunities,
                already_applied_opportunities, already_reviewed_opportunities,
                evaluations_required, evaluations_reused, llm_calls_avoided,
                provider_metrics_json, source_summary_json, health_records_json
            ) VALUES (?, 1, ?, ?, 'COMPLETED', ?, 8, ?, ?, ?, 0, 0, 0, 0, ?, ?, 0, 0, ?, ?, ?);
            """,
            (
                run_id,
                results_data.get("generated_at", "2026-08-19T19:00:00Z"),
                results_data.get("generated_at", "2026-08-19T19:00:00Z"),
                results_data.get("candidate_cv", "Tushar_Chaand_CV.docx"),
                results_data.get("total_raw_jobs", total_json_opps),
                total_json_opps,
                total_json_opps,
                total_json_reviews,
                total_json_evals,
                json.dumps(results_data.get("provider_metrics", {})),
                json.dumps(results_data.get("source_summary", [])),
                json.dumps(results_data.get("health_records", [])),
            ),
        )

        # B. Insert Opportunities and Opportunity Sources
        for idx, item in enumerate(results_list, 1):
            opp_id = f"disc_{idx:04d}"
            title = item.get("title", "")
            company = item.get("company", "")
            location = item.get("location", "")
            ckey = compute_canonical_key(title, company, location)
            desc = item.get("description", "")
            dhash = compute_content_hash(desc)

            # Review status if already reviewed
            rev = reviews_dict.get(opp_id, {})
            curr_opp_status = rev.get("opportunity_status", "UNKNOWN")
            curr_app_status = rev.get("application_status", "NOT_APPLIED")

            conn.execute(
                """
                INSERT OR REPLACE INTO opportunities (
                    id, canonical_key, title, normalized_title, company, normalized_company,
                    location, normalized_location_json, description, description_hash,
                    job_url, job_type, salary_min, salary_max, salary_interval, currency, salary_raw,
                    is_remote, first_seen_run_id, first_seen_at, last_seen_run_id, last_seen_at,
                    appearance_count, presence_status, current_opportunity_status, current_application_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'run_0001', ?, 'run_0001', ?, 1, 'AVAILABLE', ?, ?, ?, ?);
                """,
                (
                    opp_id,
                    ckey,
                    title,
                    title.strip().lower(),
                    company,
                    company.strip().lower(),
                    location,
                    json.dumps(item.get("normalized_location", {})),
                    desc,
                    dhash,
                    item.get("job_url", ""),
                    item.get("job_type", "fulltime"),
                    item.get("salary_min"),
                    item.get("salary_max"),
                    item.get("salary_interval", ""),
                    item.get("currency"),
                    item.get("salary_raw", ""),
                    1 if item.get("is_remote") else 0,
                    item.get("date_posted") or "2026-08-19",
                    item.get("date_posted") or "2026-08-19",
                    curr_opp_status,
                    curr_app_status,
                    item.get("date_posted") or "2026-08-19",
                    item.get("date_posted") or "2026-08-19",
                ),
            )

            # Insert opportunity sources
            prov_data = item.get("provenance", {})
            sources = prov_data.get("sources", [item.get("source", "unknown")])
            providers = prov_data.get("providers", ["jobspy"])
            search_q = prov_data.get("search_query", "")
            hyp_id = prov_data.get("hypothesis_id", "")
            opp_type = prov_data.get("opportunity_type", "")
            hyp_concept = prov_data.get("hypothesis_concept", "")

            for s in sources:
                p = "jobspipe" if s == "jobspipe" or "jobspipe" in providers else "jobspy"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO opportunity_sources (
                        opportunity_id, provider, source, job_url, search_query, hypothesis_id,
                        opportunity_type, hypothesis_concept, discovered_at, discovery_run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'run_0001');
                    """,
                    (opp_id, p, s, item.get("job_url", ""), search_q, hyp_id, opp_type, hyp_concept, item.get("date_posted") or "2026-08-19"),
                )

            # Insert discovery run opportunity manifest
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_run_opportunities (
                    discovery_run_id, opportunity_id, discovery_classification, rank_in_run, created_at
                ) VALUES ('run_0001', ?, 'NEW', ?, ?);
                """,
                (opp_id, idx, item.get("date_posted") or "2026-08-19"),
            )

        # C. Insert LLM Evaluations
        eval_map_by_id = {}
        for ev in evals_list:
            jid = ev.get("discovery_id") or ev.get("job_id")
            if jid:
                eval_map_by_id[jid] = ev

        for opp_idx in range(1, total_json_opps + 1):
            opp_id = f"disc_{opp_idx:04d}"
            ev = eval_map_by_id.get(opp_id)
            if ev:
                llm_eval = ev.get("llm_evaluation", {}) or {}
                eval_id = f"eval_{opp_id}"

                # Comprehensive mapping of structured fit dimensions
                fit_dims = {
                    "role_fit": llm_eval.get("role_fit"),
                    "experience_fit": llm_eval.get("current_experience_fit"),
                    "transferable": llm_eval.get("transferable_capability_fit"),
                    "seniority_fit": llm_eval.get("seniority_fit"),
                    "opportunity_alignment": llm_eval.get("opportunity_alignment"),
                    "probability_of_obtaining": llm_eval.get("probability_of_obtaining"),
                    "transition_difficulty": llm_eval.get("transition_difficulty"),
                    "career_upside": llm_eval.get("career_upside"),
                    "compensation_upside": llm_eval.get("compensation_upside"),
                    "confidence": llm_eval.get("confidence"),
                    "evidence": llm_eval.get("evidence"),
                    "missing_evidence": llm_eval.get("missing_evidence"),
                }

                # Structured scores and lists
                overall_score = llm_eval.get("overall_score") if llm_eval.get("overall_score") is not None else llm_eval.get("score")
                strengths = llm_eval.get("key_strengths") if llm_eval.get("key_strengths") is not None else llm_eval.get("strengths", [])
                gaps = llm_eval.get("missing_critical_skills") if llm_eval.get("missing_critical_skills") is not None else llm_eval.get("gaps", [])
                recommendation = llm_eval.get("recommendation")
                reasoning = llm_eval.get("reasoning", "")

                conn.execute(
                    """
                    INSERT OR REPLACE INTO evaluations (
                        id, opportunity_id, recommendation, score, fit_dimensions_json,
                        strengths_json, gaps_json, reasoning, gate_failed, gate_failure_reasons_json,
                        gate_passed_checks_json, evaluated_at, evaluator_model, content_hash,
                        is_reused, reuse_type, source_evaluation_id, reuse_reason, evaluation_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'gemini-1.5-flash', ?, 0, NULL, NULL, NULL, 'EVALUATED');
                    """,
                    (
                        eval_id,
                        opp_id,
                        recommendation,
                        overall_score,
                        json.dumps(fit_dims),
                        json.dumps(strengths),
                        json.dumps(gaps),
                        reasoning,
                        1 if ev.get("gate_failed") else 0,
                        json.dumps(ev.get("gate_failure_reasons", [])),
                        json.dumps(ev.get("gate_passed_checks", [])),
                        "2026-08-19T19:00:00Z",
                        compute_content_hash(ev.get("description", "")),
                    ),
                )

        # D. Insert Human Reviews & Initial Status History
        for jid, rev in reviews_dict.items():
            conn.execute(
                """
                INSERT OR REPLACE INTO human_reviews (
                    opportunity_id, verdict, counterfactual, priority, opportunity_status, application_status,
                    notes, opportunity_type, search_query, source, reviewed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    jid,
                    rev.get("verdict", "").upper(),
                    rev.get("counterfactual", "").upper(),
                    rev.get("priority", "").upper(),
                    rev.get("opportunity_status", "AVAILABLE").upper(),
                    rev.get("application_status", "NOT_APPLIED").upper(),
                    rev.get("notes", ""),
                    rev.get("opportunity_type"),
                    rev.get("search_query"),
                    rev.get("source"),
                    rev.get("reviewed_at", "2026-08-19T19:00:00Z"),
                    rev.get("reviewed_at", "2026-08-19T19:00:00Z"),
                ),
            )

            # Record initial history
            conn.execute(
                """
                INSERT INTO application_status_history (
                    opportunity_id, previous_status, new_status, changed_at, notes
                ) VALUES (?, 'NOT_APPLIED', ?, ?, ?);
                """,
                (
                    jid,
                    rev.get("application_status", "NOT_APPLIED").upper(),
                    rev.get("reviewed_at", "2026-08-19T19:00:00Z"),
                    rev.get("notes", "Migrated historical review"),
                ),
            )

    # 5. Dynamic Reconciliation Gate
    with repo.connection() as conn:
        db_opps_count = conn.execute("SELECT COUNT(*) FROM opportunities;").fetchone()[0]
        db_evals_count = conn.execute("SELECT COUNT(*) FROM evaluations;").fetchone()[0]
        db_reviews_count = conn.execute("SELECT COUNT(*) FROM human_reviews;").fetchone()[0]
        db_sources_count = conn.execute("SELECT COUNT(*) FROM opportunity_sources;").fetchone()[0]
        db_run_opps_count = conn.execute("SELECT COUNT(*) FROM discovery_run_opportunities WHERE discovery_run_id = 'run_0001';").fetchone()[0]

    report = {
        "historical_opportunities_json": total_json_opps,
        "sqlite_opportunities": db_opps_count,
        "historical_evaluations_json": total_json_evals,
        "sqlite_evaluations": db_evals_count,
        "historical_human_reviews_json": total_json_reviews,
        "sqlite_human_reviews": db_reviews_count,
        "sqlite_opportunity_sources": db_sources_count,
        "sqlite_run_0001_manifest": db_run_opps_count,
        "unmatched_opportunities": abs(total_json_opps - db_opps_count),
        "unmatched_evaluations": abs(total_json_evals - db_evals_count),
        "unmatched_reviews": abs(total_json_reviews - db_reviews_count),
        "results_json_sha256_verified": res_hash == EXPECTED_RESULTS_SHA256,
        "evals_json_sha256_verified": eval_hash == EXPECTED_EVALS_SHA256,
    }

    log.info("\n" + "=" * 65)
    log.info("RECONCILIATION REPORT")
    log.info("-" * 65)
    for k, v in report.items():
        log.info(f"{k:<35} : {v}")
    log.info("=" * 65)

    passed = (
        report["unmatched_opportunities"] == 0
        and report["unmatched_evaluations"] == 0
        and report["unmatched_reviews"] == 0
        and report["results_json_sha256_verified"]
        and report["evals_json_sha256_verified"]
    )

    if not passed:
        log.error("RECONCILIATION GATE FAILED! SQLite will NOT be activated.")
        return False, report

    log.info("RECONCILIATION GATE PASSED 100%. SQLite persistence verified.")
    return True, report


if __name__ == "__main__":
    success, rep = run_migration()
    if not success:
        sys.exit(1)
