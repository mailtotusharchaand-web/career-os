"""
career_os.db.repository — Data Access Layer for Career OS SQLite Database.
Provides robust parameterized queries, transaction safety, and clean models.
"""

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

DB_FILE_DEFAULT = "career_os.db"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def compute_canonical_key(title: str, company: str, location: str) -> str:
    """Deterministic hash for opportunity identity: (normalized_title, normalized_company, normalized_location)."""
    t = (title or "").strip().lower()
    c = (company or "").strip().lower()
    loc = (location or "").strip().lower()
    raw = f"{t}||{c}||{loc}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_content_hash(text: str) -> str:
    """Deterministic SHA256 hash of cleaned text content."""
    cleaned = " ".join((text or "").strip().split()).lower()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


class CareerOSRepository:
    def __init__(self, db_path: str = DB_FILE_DEFAULT):
        self.db_path = db_path

    @contextmanager
    def connection(self):
        """Context manager providing a SQLite connection with foreign keys and WAL enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initializes database schema from schema.sql if not already present."""
        if not SCHEMA_FILE.exists():
            raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE}")
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            ddl = f.read()
        with self.connection() as conn:
            conn.executescript(ddl)

    # ---------------------------------------------------------
    # Discovery Runs
    # ---------------------------------------------------------
    def get_latest_run_number(self) -> int:
        with self.connection() as conn:
            cur = conn.execute("SELECT MAX(run_number) as max_num FROM discovery_runs;")
            row = cur.fetchone()
            return row["max_num"] if row and row["max_num"] is not None else 0

    def insert_discovery_run(self, run_data: Dict[str, Any]) -> str:
        run_id = run_data.get("id") or f"run_{run_data.get('run_number', 1):04d}"
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO discovery_runs (
                    id, run_number, started_at, completed_at, status, cv_path, max_budget,
                    total_raw_records, total_unique_opportunities, new_opportunities,
                    previously_seen_opportunities, reappeared_opportunities, expired_opportunities,
                    already_applied_opportunities, already_reviewed_opportunities,
                    evaluations_required, evaluations_reused, llm_calls_avoided,
                    provider_metrics_json, source_summary_json, health_records_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    run_data.get("run_number", 1),
                    run_data.get("started_at", datetime.now(timezone.utc).isoformat()),
                    run_data.get("completed_at"),
                    run_data.get("status", "IN_PROGRESS"),
                    run_data.get("cv_path"),
                    run_data.get("max_budget"),
                    run_data.get("total_raw_records", 0),
                    run_data.get("total_unique_opportunities", 0),
                    run_data.get("new_opportunities", 0),
                    run_data.get("previously_seen_opportunities", 0),
                    run_data.get("reappeared_opportunities", 0),
                    run_data.get("expired_opportunities", 0),
                    run_data.get("already_applied_opportunities", 0),
                    run_data.get("already_reviewed_opportunities", 0),
                    run_data.get("evaluations_required", 0),
                    run_data.get("evaluations_reused", 0),
                    run_data.get("llm_calls_avoided", 0),
                    json.dumps(run_data.get("provider_metrics", {})),
                    json.dumps(run_data.get("source_summary", [])),
                    json.dumps(run_data.get("health_records", [])),
                ),
            )
        return run_id

    def update_discovery_run(self, run_id: str, updates: Dict[str, Any]) -> None:
        fields = []
        values = []
        for k, v in updates.items():
            if k in ("provider_metrics", "source_summary", "health_records"):
                fields.append(f"{k}_json = ?")
                values.append(json.dumps(v))
            else:
                fields.append(f"{k} = ?")
                values.append(v)
        values.append(run_id)
        sql = f"UPDATE discovery_runs SET {', '.join(fields)} WHERE id = ?;"
        with self.connection() as conn:
            conn.execute(sql, tuple(values))

    # ---------------------------------------------------------
    # Opportunities
    # ---------------------------------------------------------
    def get_opportunity_by_key(self, canonical_key: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT * FROM opportunities WHERE canonical_key = ?;", (canonical_key,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_opportunity_by_id(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT * FROM opportunities WHERE id = ?;", (opportunity_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def insert_opportunity(self, opp: Dict[str, Any]) -> str:
        opp_id = opp.get("id")
        canonical_key = opp.get("canonical_key") or compute_canonical_key(
            opp.get("title", ""), opp.get("company", ""), opp.get("location", "")
        )
        desc = opp.get("description", "")
        desc_hash = opp.get("description_hash") or compute_content_hash(desc)
        now = datetime.now(timezone.utc).isoformat()

        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO opportunities (
                    id, canonical_key, title, normalized_title, company, normalized_company,
                    location, normalized_location_json, description, description_hash,
                    job_url, job_type, salary_min, salary_max, salary_interval, currency, salary_raw,
                    is_remote, first_seen_run_id, first_seen_at, last_seen_run_id, last_seen_at,
                    appearance_count, presence_status, current_opportunity_status, current_application_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    opp_id,
                    canonical_key,
                    opp.get("title", ""),
                    opp.get("normalized_title", opp.get("title", "").strip().lower()),
                    opp.get("company", ""),
                    opp.get("normalized_company", opp.get("company", "").strip().lower()),
                    opp.get("location", ""),
                    json.dumps(opp.get("normalized_location", {})),
                    desc,
                    desc_hash,
                    opp.get("job_url", ""),
                    opp.get("job_type", "fulltime"),
                    opp.get("salary_min"),
                    opp.get("salary_max"),
                    opp.get("salary_interval", ""),
                    opp.get("currency"),
                    opp.get("salary_raw", ""),
                    1 if opp.get("is_remote") else 0,
                    opp.get("first_seen_run_id", "run_0001"),
                    opp.get("first_seen_at", now),
                    opp.get("last_seen_run_id", "run_0001"),
                    opp.get("last_seen_at", now),
                    opp.get("appearance_count", 1),
                    opp.get("presence_status", "AVAILABLE"),
                    opp.get("current_opportunity_status", "UNKNOWN"),
                    opp.get("current_application_status", "NOT_APPLIED"),
                    opp.get("created_at", now),
                    opp.get("updated_at", now),
                ),
            )
        return opp_id

    def mark_opportunity_seen(self, opportunity_id: str, run_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE opportunities
                SET last_seen_run_id = ?,
                    last_seen_at = ?,
                    appearance_count = appearance_count + 1,
                    presence_status = 'AVAILABLE',
                    updated_at = ?
                WHERE id = ?;
                """,
                (run_id, now, now, opportunity_id),
            )

    def mark_opportunity_disappeared(self, opportunity_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE opportunities
                SET presence_status = 'DISAPPEARED',
                    updated_at = ?
                WHERE id = ?;
                """,
                (now, opportunity_id),
            )

    def record_application_transition(self, opportunity_id: str, new_status: str, notes: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            cur = conn.execute("SELECT current_application_status FROM opportunities WHERE id = ?;", (opportunity_id,))
            row = cur.fetchone()
            prev_status = row["current_application_status"] if row else "NOT_APPLIED"

            conn.execute(
                """
                UPDATE opportunities
                SET current_application_status = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (new_status, now, opportunity_id),
            )

            conn.execute(
                """
                INSERT INTO application_status_history (
                    opportunity_id, previous_status, new_status, changed_at, notes
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (opportunity_id, prev_status, new_status, now, notes),
            )

    def insert_opportunity_source(self, source_data: Dict[str, Any]) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO opportunity_sources (
                    opportunity_id, provider, source, external_job_id, job_url, search_query,
                    hypothesis_id, opportunity_type, hypothesis_concept, discovered_at, discovery_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    source_data["opportunity_id"],
                    source_data.get("provider", "jobspy"),
                    source_data.get("source", "unknown"),
                    source_data.get("external_job_id"),
                    source_data.get("job_url", ""),
                    source_data.get("search_query", ""),
                    source_data.get("hypothesis_id", ""),
                    source_data.get("opportunity_type", ""),
                    source_data.get("hypothesis_concept", ""),
                    source_data.get("discovered_at", datetime.now(timezone.utc).isoformat()),
                    source_data.get("discovery_run_id", "run_0001"),
                ),
            )

    def insert_run_opportunity(self, run_id: str, opp_id: str, classification: str, rank: int = 1) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO discovery_run_opportunities (
                    discovery_run_id, opportunity_id, discovery_classification, rank_in_run, created_at
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (run_id, opp_id, classification, rank, datetime.now(timezone.utc).isoformat()),
            )

    # ---------------------------------------------------------
    # LLM Evaluations
    # ---------------------------------------------------------
    def insert_evaluation(self, eval_data: Dict[str, Any]) -> str:
        eval_id = eval_data.get("id") or f"eval_{eval_data['opportunity_id']}"
        now = datetime.now(timezone.utc).isoformat()
        eval_status = eval_data.get("evaluation_status")
        if not eval_status:
            eval_status = "REUSED" if eval_data.get("is_reused") else "EVALUATED"
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO evaluations (
                    id, opportunity_id, recommendation, score, fit_dimensions_json,
                    strengths_json, gaps_json, reasoning, gate_failed, gate_failure_reasons_json,
                    gate_passed_checks_json, evaluated_at, evaluator_model, content_hash,
                    is_reused, reuse_type, source_evaluation_id, reuse_reason, evaluation_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    eval_id,
                    eval_data["opportunity_id"],
                    eval_data.get("recommendation"),
                    eval_data.get("score"),
                    json.dumps(eval_data.get("fit_dimensions", {})),
                    json.dumps(eval_data.get("strengths", [])),
                    json.dumps(eval_data.get("gaps", [])),
                    eval_data.get("reasoning", ""),
                    1 if eval_data.get("gate_failed") else 0,
                    json.dumps(eval_data.get("gate_failure_reasons", [])),
                    json.dumps(eval_data.get("gate_passed_checks", [])),
                    eval_data.get("evaluated_at", now),
                    eval_data.get("evaluator_model", "gemini-1.5-flash"),
                    eval_data.get("content_hash", compute_content_hash(eval_data.get("description", ""))),
                    1 if eval_data.get("is_reused") else 0,
                    eval_data.get("reuse_type"),
                    eval_data.get("source_evaluation_id"),
                    eval_data.get("reuse_reason"),
                    eval_status,
                ),
            )
        return eval_id

    def get_evaluation_by_opportunity_id(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT * FROM evaluations WHERE opportunity_id = ? ORDER BY evaluated_at DESC LIMIT 1;", (opportunity_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["fit_dimensions"] = json.loads(res["fit_dimensions_json"] or "{}")
            res["strengths"] = json.loads(res["strengths_json"] or "[]")
            res["gaps"] = json.loads(res["gaps_json"] or "[]")
            res["gate_failure_reasons"] = json.loads(res["gate_failure_reasons_json"] or "[]")
            res["gate_passed_checks"] = json.loads(res["gate_passed_checks_json"] or "[]")
            return res

    def find_reusable_evaluation(self, opp_data: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], str, str]]:
        """
        Conservative Evaluation Reuse Hierarchy:
        - Level 1: Exact Same Opportunity previously evaluated -> (eval, 'REUSED_EXACT', reason)
        - Level 2: Same Posting URL or exact Description Hash across providers -> (eval, 'REUSED_SAME_POSTING', reason)
        - Level 3: Same Company + Exact Role Content Hash -> (eval, 'REUSED_EQUIVALENT_ROLE', reason)
        - Else: None (Requires fresh LLM evaluation)
        """
        opp_id = opp_data.get("id")
        canonical_key = opp_data.get("canonical_key") or compute_canonical_key(
            opp_data.get("title", ""), opp_data.get("company", ""), opp_data.get("location", "")
        )
        desc_hash = opp_data.get("description_hash") or compute_content_hash(opp_data.get("description", ""))
        norm_company = opp_data.get("normalized_company") or opp_data.get("company", "").strip().lower()

        # Helper to check if an evaluation record is complete and usable
        def is_valid_eval(ev: Optional[Dict[str, Any]]) -> bool:
            if not ev:
                return False
            status = ev.get("evaluation_status")
            if status not in ("EVALUATED", "REUSED"):
                return False
            return bool(ev.get("recommendation") or ev.get("gate_failed") or ev.get("score") is not None)

        # Level 1: By opportunity_id if exists
        if opp_id:
            existing = self.get_evaluation_by_opportunity_id(opp_id)
            if is_valid_eval(existing):
                return existing, "REUSED_EXACT", f"Exact opportunity ID match: {opp_id}"

        # Level 1 by canonical key
        existing_opp = self.get_opportunity_by_key(canonical_key)
        if existing_opp:
            existing_eval = self.get_evaluation_by_opportunity_id(existing_opp["id"])
            if is_valid_eval(existing_eval):
                return existing_eval, "REUSED_EXACT", f"Exact canonical key match: {existing_opp['id']}"

        # Level 2 (Same Posting) & Level 3 (Equivalent Role / Different Location)
        with self.connection() as conn:
            cur = conn.execute(
                """
                SELECT e.*, o.title, o.company, o.normalized_company, o.location, o.job_url
                FROM evaluations e
                JOIN opportunities o ON e.opportunity_id = o.id
                WHERE o.description_hash = ?
                  AND e.evaluation_status IN ('EVALUATED', 'REUSED')
                  AND (e.recommendation IS NOT NULL OR e.gate_failed = 1 OR e.score IS NOT NULL)
                  AND o.id != ?
                ORDER BY e.evaluated_at DESC LIMIT 1;
                """,
                (desc_hash, opp_id or "")
            )
            row = cur.fetchone()
            if row:
                row_norm_comp = (row["normalized_company"] or row["company"] or "").strip().lower()
                row_loc = (row["location"] or "").strip().lower()
                req_loc = (opp_data.get("location") or "").strip().lower()

                # Guard against different companies sharing generic descriptions
                if norm_company and row_norm_comp and norm_company == row_norm_comp:
                    res = dict(row)
                    res["fit_dimensions"] = json.loads(res["fit_dimensions_json"] or "{}")
                    res["strengths"] = json.loads(res["strengths_json"] or "[]")
                    res["gaps"] = json.loads(res["gaps_json"] or "[]")
                    res["gate_failure_reasons"] = json.loads(res["gate_failure_reasons_json"] or "[]")
                    res["gate_passed_checks"] = json.loads(res["gate_passed_checks_json"] or "[]")

                    if req_loc and row_loc and req_loc != row_loc:
                        return res, "REUSED_EQUIVALENT_ROLE", f"Equivalent role at same company '{row['company']}' in different location ({req_loc} vs {row_loc})"
                    else:
                        return res, "REUSED_SAME_POSTING", f"Identical job posting match from {row['company']}"

        return None

    # ---------------------------------------------------------
    # Human Reviews & Application Lifecycle
    # ---------------------------------------------------------
    def get_human_review(self, opportunity_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT * FROM human_reviews WHERE opportunity_id = ?;", (opportunity_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def list_all_human_reviews(self) -> Dict[str, Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT * FROM human_reviews;")
            res = {}
            for r in cur.fetchall():
                d = dict(r)
                d["job_id"] = d["opportunity_id"]
                res[d["opportunity_id"]] = d
            return res

    def save_human_review(self, review_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Saves human review transactionally in SQLite, updates opportunity statuses,
        and logs application status transition if changed.
        """
        opp_id = review_data["opportunity_id"]
        verdict = review_data.get("verdict", "").upper()
        counterfactual = review_data.get("counterfactual", "").upper()
        priority = review_data.get("priority", "").upper()
        opp_status = review_data.get("opportunity_status", "AVAILABLE").upper()
        app_status = review_data.get("application_status", "NOT_APPLIED").upper()
        notes = review_data.get("notes", "")
        now = datetime.now(timezone.utc).isoformat()

        with self.connection() as conn:
            # Check previous application status for audit log
            cur = conn.execute("SELECT current_application_status FROM opportunities WHERE id = ?;", (opp_id,))
            row = cur.fetchone()
            prev_app_status = row["current_application_status"] if row else "NOT_APPLIED"

            # Upsert human review
            conn.execute(
                """
                INSERT INTO human_reviews (
                    opportunity_id, verdict, counterfactual, priority, opportunity_status, application_status,
                    notes, opportunity_type, search_query, source, reviewed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(opportunity_id) DO UPDATE SET
                    verdict = excluded.verdict,
                    counterfactual = excluded.counterfactual,
                    priority = excluded.priority,
                    opportunity_status = excluded.opportunity_status,
                    application_status = excluded.application_status,
                    notes = excluded.notes,
                    opportunity_type = COALESCE(excluded.opportunity_type, human_reviews.opportunity_type),
                    search_query = COALESCE(excluded.search_query, human_reviews.search_query),
                    source = COALESCE(excluded.source, human_reviews.source),
                    updated_at = excluded.updated_at;
                """,
                (
                    opp_id,
                    verdict,
                    counterfactual,
                    priority,
                    opp_status,
                    app_status,
                    notes,
                    review_data.get("opportunity_type"),
                    review_data.get("search_query"),
                    review_data.get("source"),
                    review_data.get("reviewed_at", now),
                    now,
                ),
            )

            # Update opportunity current status
            conn.execute(
                """
                UPDATE opportunities
                SET current_opportunity_status = ?,
                    current_application_status = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (opp_status, app_status, now, opp_id),
            )

            # Record history if application status changed
            if prev_app_status != app_status:
                conn.execute(
                    """
                    INSERT INTO application_status_history (
                        opportunity_id, previous_status, new_status, changed_at, notes
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (opp_id, prev_app_status, app_status, now, notes),
                )

        return {
            "job_id": opp_id,
            "opportunity_id": opp_id,
            "verdict": verdict,
            "counterfactual": counterfactual,
            "priority": priority,
            "opportunity_status": opp_status,
            "application_status": app_status,
            "notes": notes,
            "reviewed_at": review_data.get("reviewed_at", now),
            "updated_at": now,
        }

    # ---------------------------------------------------------
    # Workstation View & Summary Aggregation
    # ---------------------------------------------------------
    def get_workstation_data(self) -> Dict[str, Any]:
        """
        Loads all opportunities, attached LLM evaluations, and human review decisions
        formatted exactly to match the review workstation API contract.
        """
        with self.connection() as conn:
            # 1. Fetch opportunities
            cur = conn.execute(
                """
                SELECT o.*,
                       e.recommendation, e.score, e.fit_dimensions_json, e.strengths_json,
                       e.gaps_json, e.reasoning, e.gate_failed, e.gate_failure_reasons_json,
                       e.gate_passed_checks_json, e.is_reused, e.reuse_type, e.source_evaluation_id,
                       e.evaluation_status
                FROM opportunities o
                LEFT JOIN evaluations e ON o.id = e.opportunity_id
                ORDER BY o.id ASC;
                """
            )
            rows = cur.fetchall()

            # 2. Fetch sources per opportunity
            src_cur = conn.execute("SELECT * FROM opportunity_sources ORDER BY id ASC;")
            sources_by_opp: Dict[str, List[Dict[str, Any]]] = {}
            for s in src_cur.fetchall():
                oid = s["opportunity_id"]
                if oid not in sources_by_opp:
                    sources_by_opp[oid] = []
                sources_by_opp[oid].append(dict(s))

            # 3. Assemble jobs
            jobs = []
            for idx, r in enumerate(rows, 1):
                opp_id = r["id"]
                opp_sources = sources_by_opp.get(opp_id, [])
                src_names = [s["source"] for s in opp_sources] if opp_sources else [r["company"]]
                prov_names = list(set([s["provider"] for s in opp_sources])) if opp_sources else ["jobspy"]
                first_src = opp_sources[0] if opp_sources else {}

                eval_status = r["evaluation_status"]
                if r["gate_failed"]:
                    eval_status = "GATE_REJECTED"
                elif not eval_status:
                    if r["is_reused"]:
                        eval_status = "REUSED"
                    elif r["recommendation"] is not None or r["reasoning"] or r["score"] is not None:
                        eval_status = "EVALUATED"
                    else:
                        eval_status = "PENDING"

                job_obj = {
                    "job_id": opp_id,
                    "id": opp_id,
                    "rank": idx,
                    "title": r["title"],
                    "company": r["company"],
                    "location": r["location"],
                    "description": r["description"],
                    "job_url": r["job_url"],
                    "source": src_names[0] if src_names else "unknown",
                    "job_type": r["job_type"],
                    "salary_min": r["salary_min"],
                    "salary_max": r["salary_max"],
                    "salary_interval": r["salary_interval"],
                    "currency": r["currency"],
                    "salary_raw": r["salary_raw"],
                    "is_remote": bool(r["is_remote"]),
                    "date_posted": r["first_seen_at"][:10],
                    "presence_status": r["presence_status"],
                    "current_opportunity_status": r["current_opportunity_status"],
                    "current_application_status": r["current_application_status"],
                    "evaluation_status": eval_status,
                    "normalized_location": json.loads(r["normalized_location_json"] or "{}"),
                    "provenance": {
                        "sources": src_names,
                        "providers": prov_names,
                        "search_query": first_src.get("search_query", ""),
                        "hypothesis_id": first_src.get("hypothesis_id", ""),
                        "opportunity_type": first_src.get("opportunity_type", ""),
                        "hypothesis_concept": first_src.get("hypothesis_concept", ""),
                        "retrieved_at": r["first_seen_at"],
                    },
                }

                # Attach evaluation details if present and not PENDING
                if eval_status in ("EVALUATED", "REUSED") and (r["recommendation"] is not None or r["reasoning"] or r["score"] is not None):
                    fit_dims = json.loads(r["fit_dimensions_json"] or "{}")
                    strengths = json.loads(r["strengths_json"] or "[]")
                    gaps = json.loads(r["gaps_json"] or "[]")
                    score = r["score"]

                    llm_eval_obj = {
                        "recommendation": r["recommendation"],
                        "score": score,
                        "overall_score": score,
                        "reasoning": r["reasoning"],
                        "strengths": strengths,
                        "key_strengths": strengths,
                        "gaps": gaps,
                        "missing_critical_skills": gaps,
                        "fit_dimensions": fit_dims,
                        "role_fit": fit_dims.get("role_fit"),
                        "current_experience_fit": fit_dims.get("experience_fit"),
                        "transferable_capability_fit": fit_dims.get("transferable"),
                        "seniority_fit": fit_dims.get("seniority_fit"),
                        "opportunity_alignment": fit_dims.get("opportunity_alignment"),
                        "probability_of_obtaining": fit_dims.get("probability_of_obtaining"),
                        "transition_difficulty": fit_dims.get("transition_difficulty"),
                        "career_upside": fit_dims.get("career_upside"),
                        "compensation_upside": fit_dims.get("compensation_upside"),
                        "confidence": fit_dims.get("confidence"),
                        "evidence": fit_dims.get("evidence"),
                        "missing_evidence": fit_dims.get("missing_evidence"),
                        "is_reused": bool(r["is_reused"]),
                        "reuse_type": r["reuse_type"],
                        "source_evaluation_id": r["source_evaluation_id"],
                        "evaluation_status": eval_status,
                    }
                    job_obj["llm_evaluation"] = llm_eval_obj
                    job_obj["gate_failed"] = bool(r["gate_failed"])
                    job_obj["gate_failure_reasons"] = json.loads(r["gate_failure_reasons_json"] or "[]")
                    job_obj["gate_passed_checks"] = json.loads(r["gate_passed_checks_json"] or "[]")
                else:
                    job_obj["llm_evaluation"] = None
                    job_obj["gate_failed"] = bool(r["gate_failed"]) if r["gate_failed"] is not None else False
                    job_obj["gate_failure_reasons"] = json.loads(r["gate_failure_reasons_json"] or "[]")
                    job_obj["gate_passed_checks"] = json.loads(r["gate_passed_checks_json"] or "[]")

                jobs.append(job_obj)

            # 4. Fetch latest discovery run metadata if any
            run_cur = conn.execute("SELECT * FROM discovery_runs ORDER BY run_number DESC LIMIT 1;")
            latest_run = run_cur.fetchone()
            gen_at = latest_run["completed_at"] or latest_run["started_at"] if latest_run else None
            source_summary = json.loads(latest_run["source_summary_json"] or "[]") if latest_run else []

            return {
                "jobs": jobs,
                "total_unique_deduped": len(jobs),
                "generated_at": gen_at,
                "source_stats": {s["source"]: {"status": s.get("health", "SUCCESS_WITH_RESULTS")} for s in source_summary} if source_summary else {},
            }

    def compute_summary_stats(self) -> Dict[str, Any]:
        """Computes aggregate and breakdown statistics directly from SQLite."""
        with self.connection() as conn:
            # 1. Total & Reviewed counts
            total_opps = conn.execute("SELECT COUNT(*) FROM opportunities;").fetchone()[0]
            total_reviewed = conn.execute("SELECT COUNT(*) FROM human_reviews;").fetchone()[0]
            unreviewed = max(0, total_opps - total_reviewed)

            # 2. Verdicts & Counterfactuals
            verdicts = {"RELEVANT": 0, "ADJACENT": 0, "WEAK": 0, "IRRELEVANT": 0}
            for r in conn.execute("SELECT verdict, COUNT(*) as cnt FROM human_reviews GROUP BY verdict;").fetchall():
                v = (r["verdict"] or "").upper()
                if v in verdicts:
                    verdicts[v] = r["cnt"]

            counterfactuals = {"YES": 0, "PROBABLY": 0, "NO": 0, "UNSURE": 0}
            for r in conn.execute("SELECT counterfactual, COUNT(*) as cnt FROM human_reviews GROUP BY counterfactual;").fetchall():
                cf = (r["counterfactual"] or "").upper()
                if cf in counterfactuals:
                    counterfactuals[cf] = r["cnt"]

            # 3. Opportunity & Application Statuses
            opp_statuses = {"UNKNOWN": 0, "AVAILABLE": 0, "EXPIRED": 0}
            for r in conn.execute("SELECT current_opportunity_status, COUNT(*) as cnt FROM opportunities GROUP BY current_opportunity_status;").fetchall():
                st = (r["current_opportunity_status"] or "").upper()
                if st in opp_statuses:
                    opp_statuses[st] = r["cnt"]

            app_statuses = {
                "NOT_APPLIED": 0, "READY_TO_APPLY": 0, "APPLIED": 0,
                "RECRUITER_CONTACT": 0, "INTERVIEW": 0, "REJECTED": 0,
                "WITHDRAWN": 0, "OFFER": 0,
            }
            for r in conn.execute("SELECT current_application_status, COUNT(*) as cnt FROM opportunities GROUP BY current_application_status;").fetchall():
                st = (r["current_application_status"] or "").upper()
                if st in app_statuses:
                    app_statuses[st] = r["cnt"]

            # 4. Breakdowns
            by_type = {}
            by_intent = {}
            by_source = {}

            # Join opportunities, sources, reviews
            cur = conn.execute(
                """
                SELECT o.id, os.hypothesis_id, os.search_query, os.source,
                       hr.verdict, hr.counterfactual
                FROM opportunities o
                LEFT JOIN opportunity_sources os ON o.id = os.opportunity_id
                LEFT JOIN human_reviews hr ON o.id = hr.opportunity_id;
                """
            )
            for r in cur.fetchall():
                otype = r["hypothesis_id"] or "unspecified"
                intent = r["search_query"] or "unspecified"
                src = r["source"] or "unknown"
                v = (r["verdict"] or "").upper()
                cf = (r["counterfactual"] or "").upper()
                has_rev = bool(v)

                for bdict, key in [(by_type, otype), (by_intent, intent), (by_source, src)]:
                    if key not in bdict:
                        bdict[key] = {
                            "total": 0, "reviewed": 0,
                            "RELEVANT": 0, "ADJACENT": 0, "WEAK": 0, "IRRELEVANT": 0,
                            "cf_YES": 0, "cf_PROBABLY": 0, "cf_NO": 0, "cf_UNSURE": 0,
                        }
                    bdict[key]["total"] += 1
                    if has_rev:
                        bdict[key]["reviewed"] += 1
                        if v in bdict[key]:
                            bdict[key][v] += 1
                        cf_k = f"cf_{cf}"
                        if cf_k in bdict[key]:
                            bdict[key][cf_k] += 1

            return {
                "total_discovered": total_opps,
                "total_reviewed": total_reviewed,
                "total_unreviewed": unreviewed,
                "verdicts": verdicts,
                "counterfactuals": counterfactuals,
                "opportunity_statuses": opp_statuses,
                "application_statuses": app_statuses,
                "by_opportunity_type": by_type,
                "by_search_intent": by_intent,
                "by_source": by_source,
            }

    # ---------------------------------------------------------
    # Email Sync Checkpoints & Ingestion Tracking
    # ---------------------------------------------------------
    def get_or_create_email_sync_checkpoint(self, provider: str, account_id: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            cur = conn.execute(
                "SELECT * FROM email_sync_checkpoints WHERE provider = ? AND account_id = ?;",
                (provider, account_id),
            )
            row = cur.fetchone()
            if row:
                return dict(row)

            conn.execute(
                """
                INSERT INTO email_sync_checkpoints (
                    provider, account_id, last_synced_at, last_history_id,
                    last_message_timestamp, sync_status, messages_processed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (provider, account_id, now, None, None, "HEALTHY", 0, now, now),
            )
            cur = conn.execute(
                "SELECT * FROM email_sync_checkpoints WHERE provider = ? AND account_id = ?;",
                (provider, account_id),
            )
            return dict(cur.fetchone())

    def update_email_sync_checkpoint(
        self,
        provider: str,
        account_id: str,
        last_synced_at: Optional[str] = None,
        last_history_id: Optional[str] = None,
        last_message_timestamp: Optional[str] = None,
        sync_status: Optional[str] = None,
        messages_increment: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO email_sync_checkpoints (
                    provider, account_id, last_synced_at, last_history_id,
                    last_message_timestamp, sync_status, messages_processed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, account_id) DO UPDATE SET
                    last_synced_at = COALESCE(excluded.last_synced_at, email_sync_checkpoints.last_synced_at),
                    last_history_id = COALESCE(excluded.last_history_id, email_sync_checkpoints.last_history_id),
                    last_message_timestamp = COALESCE(excluded.last_message_timestamp, email_sync_checkpoints.last_message_timestamp),
                    sync_status = COALESCE(excluded.sync_status, email_sync_checkpoints.sync_status),
                    messages_processed = email_sync_checkpoints.messages_processed + excluded.messages_processed,
                    updated_at = excluded.updated_at;
                """,
                (
                    provider,
                    account_id,
                    last_synced_at or now,
                    last_history_id,
                    last_message_timestamp,
                    sync_status or "HEALTHY",
                    messages_increment,
                    now,
                    now,
                ),
            )

    def is_raw_email_processed(self, provider: str, account_id: str, message_id: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                "SELECT 1 FROM email_raw_messages WHERE provider = ? AND account_id = ? AND message_id = ?;",
                (provider, account_id, message_id),
            )
            return cur.fetchone() is not None

    def record_raw_email(self, msg_dict: Dict[str, Any]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO email_raw_messages (
                    provider, account_id, message_id, thread_id, sender, sender_domain,
                    recipients_json, subject, snippet, body_hash, received_at, processed_at,
                    labels_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    msg_dict.get("provider", "unknown"),
                    msg_dict.get("account_id", ""),
                    msg_dict.get("message_id", ""),
                    msg_dict.get("thread_id", ""),
                    msg_dict.get("sender", ""),
                    msg_dict.get("sender_domain", ""),
                    json.dumps(msg_dict.get("recipients", [])),
                    msg_dict.get("subject", ""),
                    msg_dict.get("snippet", ""),
                    msg_dict.get("body_hash", ""),
                    msg_dict.get("received_at", now),
                    now,
                    json.dumps(msg_dict.get("labels", [])),
                    now,
                ),
            )
            return cur.lastrowid

    # ---------------------------------------------------------
    # Career Events & Application State Mutation
    # ---------------------------------------------------------
    def get_career_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cur = conn.execute("SELECT * FROM career_events WHERE id = ?;", (event_id,))
            row = cur.fetchone()
            if not row:
                return None
            res = dict(row)
            res["evidence"] = json.loads(res["evidence_json"] or "{}")
            res["candidate_matches"] = json.loads(res["candidate_matches_json"] or "[]")
            return res

    def list_career_events(
        self,
        opportunity_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM career_events WHERE 1=1"
        params = []
        if opportunity_id:
            query += " AND opportunity_id = ?"
            params.append(opportunity_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY occurred_at DESC, created_at DESC LIMIT ?;"
        params.append(limit)

        with self.connection() as conn:
            cur = conn.execute(query, tuple(params))
            results = []
            for row in cur.fetchall():
                d = dict(row)
                d["evidence"] = json.loads(d["evidence_json"] or "{}")
                d["candidate_matches"] = json.loads(d["candidate_matches_json"] or "[]")
                results.append(d)
            return results

    def record_career_event_and_transition(
        self,
        event_data: Dict[str, Any],
        raw_message_data: Optional[Dict[str, Any]] = None,
        should_mutate_status: bool = False,
        new_application_status: Optional[str] = None,
        transition_notes: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """
        Atomically records:
        1. Raw email ingestion record (if provided)
        2. CareerEvent record
        3. Application status transition (if should_mutate_status=True)
        4. Application status history audit trail
        
        Returns: (event_id, did_mutate_status)
        """
        event_id = event_data["id"]
        opp_id = event_data.get("opportunity_id")
        now = datetime.now(timezone.utc).isoformat()

        with self.connection() as conn:
            # 1. Raw email record if provided
            if raw_message_data:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO email_raw_messages (
                        provider, account_id, message_id, thread_id, sender, sender_domain,
                        recipients_json, subject, snippet, body_hash, received_at, processed_at,
                        labels_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        raw_message_data.get("provider", "unknown"),
                        raw_message_data.get("account_id", ""),
                        raw_message_data.get("message_id", ""),
                        raw_message_data.get("thread_id", ""),
                        raw_message_data.get("sender", ""),
                        raw_message_data.get("sender_domain", ""),
                        json.dumps(raw_message_data.get("recipients", [])),
                        raw_message_data.get("subject", ""),
                        raw_message_data.get("snippet", ""),
                        raw_message_data.get("body_hash", ""),
                        raw_message_data.get("received_at", now),
                        now,
                        json.dumps(raw_message_data.get("labels", [])),
                        now,
                    ),
                )

            # 2. Insert CareerEvent
            conn.execute(
                """
                INSERT INTO career_events (
                    id, event_type, opportunity_id, occurred_at, source_provider,
                    source_account_id, source_message_id, source_thread_id,
                    confidence_score, confidence_level, status, evidence_json,
                    candidate_matches_json, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_provider, source_account_id, source_message_id) DO UPDATE SET
                    status = excluded.status,
                    notes = COALESCE(excluded.notes, career_events.notes),
                    updated_at = excluded.updated_at;
                """,
                (
                    event_id,
                    event_data["event_type"],
                    opp_id,
                    event_data.get("occurred_at", now),
                    event_data["source_provider"],
                    event_data["source_account_id"],
                    event_data["source_message_id"],
                    event_data.get("source_thread_id", ""),
                    float(event_data.get("confidence_score", 0.0)),
                    event_data.get("confidence_level", "MEDIUM"),
                    event_data.get("status", "PENDING_CONFIRMATION"),
                    json.dumps(event_data.get("evidence", {})),
                    json.dumps(event_data.get("candidate_matches", [])),
                    event_data.get("notes"),
                    event_data.get("created_at", now),
                    now,
                ),
            )

            # 3. Mutate application status if requested and opportunity exists
            did_mutate = False
            if should_mutate_status and opp_id and new_application_status:
                cur = conn.execute("SELECT current_application_status FROM opportunities WHERE id = ?;", (opp_id,))
                opp_row = cur.fetchone()
                if opp_row:
                    prev_status = opp_row["current_application_status"]
                    if prev_status != new_application_status:
                        # Update opportunity
                        conn.execute(
                            """
                            UPDATE opportunities
                            SET current_application_status = ?,
                                updated_at = ?
                            WHERE id = ?;
                            """,
                            (new_application_status, now, opp_id),
                        )
                        # Append history audit trail
                        audit_note = f"[source={event_data['source_provider']}, event_id={event_id}] {transition_notes or ''}".strip()
                        conn.execute(
                            """
                            INSERT INTO application_status_history (
                                opportunity_id, previous_status, new_status, changed_at, notes
                            ) VALUES (?, ?, ?, ?, ?);
                            """,
                            (opp_id, prev_status, new_application_status, now, audit_note),
                        )
                        did_mutate = True

            return event_id, did_mutate

    def confirm_career_event(self, event_id: str, opportunity_id: str, notes: Optional[str] = None) -> bool:
        """
        Manually confirms an ambiguous/pending CareerEvent and applies its transition.
        """
        event = self.get_career_event(event_id)
        if not event:
            return False

        from career_os.email.lifecycle import LifecycleValidator
        from career_os.email.models import EventType, ConfidenceLevel

        opp = self.get_opportunity_by_id(opportunity_id)
        if not opp:
            return False

        event_type = EventType(event["event_type"])
        decision = LifecycleValidator.evaluate_transition(
            current_status=opp["current_application_status"],
            event_type=event_type,
            confidence_level=ConfidenceLevel.HIGH,
            is_actionable=True,
        )

        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE career_events
                SET opportunity_id = ?,
                    status = 'CONFIRMED',
                    notes = COALESCE(?, notes),
                    updated_at = ?
                WHERE id = ?;
                """,
                (opportunity_id, notes or "Confirmed by user.", now, event_id),
            )

            if decision.should_mutate and decision.proposed_status != opp["current_application_status"]:
                conn.execute(
                    """
                    UPDATE opportunities
                    SET current_application_status = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (decision.proposed_status, now, opportunity_id),
                )
                audit_note = f"[source=manual_confirmation, event_id={event_id}] {notes or ''}".strip()
                conn.execute(
                    """
                    INSERT INTO application_status_history (
                        opportunity_id, previous_status, new_status, changed_at, notes
                    ) VALUES (?, ?, ?, ?, ?);
                    """,
                    (opportunity_id, opp["current_application_status"], decision.proposed_status, now, audit_note),
                )

        return True

    def dismiss_career_event(self, event_id: str, notes: Optional[str] = None) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            cur = conn.execute(
                """
                UPDATE career_events
                SET status = 'REJECTED',
                    notes = COALESCE(?, notes),
                    updated_at = ?
                WHERE id = ?;
                """,
                (notes or "Dismissed by user.", now, event_id),
            )
            return cur.rowcount > 0

    def get_opportunity_timeline(self, opportunity_id: str) -> List[Dict[str, Any]]:
        """Returns consolidated timeline of status history and career events for an opportunity."""
        with self.connection() as conn:
            # 1. Fetch status history
            hist_cur = conn.execute(
                "SELECT * FROM application_status_history WHERE opportunity_id = ? ORDER BY changed_at ASC;",
                (opportunity_id,),
            )
            history = [
                {
                    "type": "STATUS_CHANGE",
                    "timestamp": r["changed_at"],
                    "previous_status": r["previous_status"],
                    "new_status": r["new_status"],
                    "notes": r["notes"],
                }
                for r in hist_cur.fetchall()
            ]

            # 2. Fetch career events
            ev_cur = conn.execute(
                "SELECT * FROM career_events WHERE opportunity_id = ? ORDER BY occurred_at ASC;",
                (opportunity_id,),
            )
            events = [
                {
                    "type": "CAREER_EVENT",
                    "id": r["id"],
                    "event_type": r["event_type"],
                    "timestamp": r["occurred_at"],
                    "confidence_level": r["confidence_level"],
                    "status": r["status"],
                    "evidence": json.loads(r["evidence_json"] or "{}"),
                    "notes": r["notes"],
                }
                for r in ev_cur.fetchall()
            ]

            timeline = history + events
            timeline.sort(key=lambda x: x["timestamp"])
            return timeline

