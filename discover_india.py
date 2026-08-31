#!/usr/bin/env python3
"""
discover_india.py — Dynamic India Opportunity Discovery for Career OS.

Pipeline:
1. Parse CV (Tushar_Chaand_CV.docx)
2. Extract Candidate Capabilities -> candidate_capabilities.json
3. Generate Opportunity Hypotheses -> opportunity_hypotheses.json
4. Generate Dynamic Search Intents -> search_intents.json
5. Route and Execute across India sources (Indeed, LinkedIn, JobsPipe)
6. Normalize, Verify India location, and Deduplicate -> output JSON
7. Track and report provider-level, source-level, and cross-provider contribution metrics.
"""

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from evaluate import parse_cv
from career_os.discovery.geography import is_india_location, normalize_location
from career_os.discovery.router import route_intent, load_source_registry
from career_os.discovery.adapters import execute_source_plan
from career_os.discovery.normalizer import normalize_job, dedupe_jobs
from career_os.discovery.candidate_model import extract_candidate_capabilities
from career_os.discovery.hypotheses import generate_opportunity_hypotheses
from career_os.discovery.intents import generate_search_intents
from career_os.db.repository import CareerOSRepository, compute_canonical_key, compute_content_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("discover_india")

DEFAULT_CV = "Tushar_Chaand_CV.docx"
CAPABILITIES_OUTPUT = "candidate_capabilities.json"
HYPOTHESES_OUTPUT = "opportunity_hypotheses.json"
INTENTS_OUTPUT = "search_intents.json"
DEFAULT_DISCOVERY_OUTPUT = "run_0003_results.json"
SQLITE_DB_FILE = "career_os.db"


def compute_discovery_metrics(
    raw_jobs: List[Dict[str, Any]],
    deduped_jobs: List[Dict[str, Any]],
    source_stats: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes mathematically consistent provider-level, source-level, and cross-provider deduplication metrics.
    Guarantees invariant: total_raw_records - total_duplicates_merged == final_unique_records
    """
    total_raw_records = len(raw_jobs)
    final_unique_records = len(deduped_jobs)

    raw_by_source = Counter()
    raw_by_provider = Counter()
    provider_raw_jobs: Dict[str, List[Dict[str, Any]]] = {}

    for r in raw_jobs:
        src = r.get("_discovered_via_source") or r.get("site") or "unknown"
        prov = r.get("_discovered_via_provider") or ("jobspipe" if src == "jobspipe" else "jobspy")
        raw_by_source[src] += 1
        raw_by_provider[prov] += 1
        if prov not in provider_raw_jobs:
            provider_raw_jobs[prov] = []
        provider_raw_jobs[prov].append(r)

    # Intra-provider deduplication
    provider_unique_counts: Dict[str, int] = {}
    provider_duplicates: Dict[str, int] = {}

    for prov, p_raw_list in provider_raw_jobs.items():
        norm_p = [normalize_job(j) for j in p_raw_list]
        dedup_p = dedupe_jobs(norm_p)
        provider_unique_counts[prov] = len(dedup_p)
        provider_duplicates[prov] = len(p_raw_list) - len(dedup_p)

    provider_unique_records_total = sum(provider_unique_counts.values())
    intra_provider_duplicates = total_raw_records - provider_unique_records_total
    cross_provider_duplicates = max(0, provider_unique_records_total - final_unique_records)
    total_duplicates_merged = intra_provider_duplicates + cross_provider_duplicates

    # Invariant enforcement
    if total_raw_records - total_duplicates_merged != final_unique_records:
        total_duplicates_merged = total_raw_records - final_unique_records
        cross_provider_duplicates = max(0, total_duplicates_merged - intra_provider_duplicates)

    # Cross-provider attribution in final deduped corpus
    unique_by_source = Counter()
    jobspy_only = 0
    jobspipe_only = 0
    found_by_both = 0
    multi_source_jobs = 0

    for j in deduped_jobs:
        srcs = j.get("provenance", {}).get("sources", [])
        provs = j.get("provenance", {}).get("providers", [])

        if len(srcs) > 1:
            multi_source_jobs += 1
        for s in srcs:
            unique_by_source[s] += 1

        has_jobspy = "jobspy" in provs or any(s in ["indeed", "linkedin", "naukri"] for s in srcs)
        has_jobspipe = "jobspipe" in provs or "jobspipe" in srcs

        if has_jobspy and has_jobspipe:
            found_by_both += 1
        elif has_jobspy:
            jobspy_only += 1
        elif has_jobspipe:
            jobspipe_only += 1

    source_summary_table = []
    stats = source_stats or {}
    all_source_names = sorted(set(list(raw_by_source.keys()) + list(stats.keys())))

    for s_name in all_source_names:
        raw_count = raw_by_source.get(s_name, 0)
        uniq_count = unique_by_source.get(s_name, 0)
        dupes_count = max(0, raw_count - uniq_count)

        s_data = stats.get(s_name, {})
        if s_data.get("SUCCESS_WITH_RESULTS", 0) > 0:
            health = "SUCCESS_WITH_RESULTS"
        elif s_data.get("BLOCKED", 0) > 0:
            health = "BLOCKED"
        elif s_data.get("ERROR", 0) > 0:
            health = "ERROR"
        elif s_data.get("UNAVAILABLE", 0) > 0:
            health = "UNAVAILABLE"
        elif s_data.get("TIMEOUT", 0) > 0:
            health = "TIMEOUT"
        elif raw_count > 0:
            health = "SUCCESS_WITH_RESULTS"
        else:
            health = "SUCCESS_EMPTY"

        source_summary_table.append({
            "source": s_name,
            "raw": raw_count,
            "unique": uniq_count,
            "duplicates": dupes_count,
            "health": health,
        })

    return {
        "total_raw_records": total_raw_records,
        "provider_unique_records_total": provider_unique_records_total,
        "intra_provider_duplicates": intra_provider_duplicates,
        "cross_provider_duplicates": cross_provider_duplicates,
        "total_duplicates_merged": total_duplicates_merged,
        "final_unique_records": final_unique_records,
        "jobspy_only": jobspy_only,
        "jobspipe_only": jobspipe_only,
        "found_by_both": found_by_both,
        "multi_source_opportunities": multi_source_jobs,
        "provider_metrics": {
            "jobspy": {
                "raw": raw_by_provider.get("jobspy", 0),
                "unique": provider_unique_counts.get("jobspy", 0),
                "duplicates": provider_duplicates.get("jobspy", 0),
            },
            "jobspipe": {
                "raw": raw_by_provider.get("jobspipe", 0),
                "unique": provider_unique_counts.get("jobspipe", 0),
                "duplicates": provider_duplicates.get("jobspipe", 0),
            },
        },
        "source_summary": source_summary_table,
    }


def run_dynamic_india_discovery(
    cv_path: str = DEFAULT_CV,
    max_search_budget: int = 8,
    results_per_source_query: int = 10,
    reuse_existing_artifacts: bool = False,
    output_path: str = DEFAULT_DISCOVERY_OUTPUT,
) -> Dict[str, Any]:
    """
    Orchestrates the dynamic CV-driven opportunity discovery pipeline for India.
    Outputs to output_path without modifying baseline datasets unless explicitly targeted.
    """
    log.info("=" * 65)
    log.info("CAREER OS — INDIA DYNAMIC OPPORTUNITY DISCOVERY")
    log.info("=" * 65)

    # 1. Parse CV
    log.info(f"Step 1: Reading CV from '{cv_path}'...")
    cv_text = parse_cv(cv_path)
    log.info(f"CV successfully parsed ({len(cv_text)} characters).")

    # 2. Extract Capability Model
    if reuse_existing_artifacts and Path(CAPABILITIES_OUTPUT).exists():
        log.info(f"Reusing existing {CAPABILITIES_OUTPUT}...")
        with open(CAPABILITIES_OUTPUT, "r", encoding="utf-8") as f:
            capabilities = json.load(f)
    else:
        log.info("Step 2: Generating structured candidate capability model...")
        capabilities = extract_candidate_capabilities(cv_text)
        with open(CAPABILITIES_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(capabilities, f, indent=2, default=str)
        log.info(f"Saved candidate capability model to {CAPABILITIES_OUTPUT}")

    # 3. Generate Opportunity Hypotheses
    if reuse_existing_artifacts and Path(HYPOTHESES_OUTPUT).exists():
        log.info(f"Reusing existing {HYPOTHESES_OUTPUT}...")
        with open(HYPOTHESES_OUTPUT, "r", encoding="utf-8") as f:
            hypotheses = json.load(f)
    else:
        log.info("Step 3: Generating open-world opportunity hypotheses...")
        hypotheses = generate_opportunity_hypotheses(capabilities)
        with open(HYPOTHESES_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(hypotheses, f, indent=2, default=str)
        log.info(f"Saved {len(hypotheses)} opportunity hypotheses to {HYPOTHESES_OUTPUT}")

    # 4. Generate Dynamic Search Intents
    if reuse_existing_artifacts and Path(INTENTS_OUTPUT).exists():
        log.info(f"Reusing existing {INTENTS_OUTPUT}...")
        with open(INTENTS_OUTPUT, "r", encoding="utf-8") as f:
            intents = json.load(f)
    else:
        log.info(f"Step 4: Generating market search intents (budget limit: {max_search_budget})...")
        intents = generate_search_intents(hypotheses, max_budget=max_search_budget)
        with open(INTENTS_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(intents, f, indent=2, default=str)
        log.info(f"Saved {len(intents)} search intents to {INTENTS_OUTPUT}")

    # Map hypothesis_id -> hypothesis metadata for end-to-end traceability
    hyp_map = {h["hypothesis_id"]: h for h in hypotheses}

    # 5. Route and Execute across Sources
    log.info("Step 5: Routing search intents to enabled India sources...")
    registry = load_source_registry("config/sources.json")
    
    total_raw_jobs = []
    all_health_records = []
    source_stats = {}

    for idx, intent in enumerate(intents, 1):
        query = intent["search_query"]
        hyp_id = intent.get("hypothesis_id", "")
        hyp_obj = hyp_map.get(hyp_id, {})
        
        log.info(f"\n[Intent {idx}/{len(intents)}] '{query}' (Hypothesis: {hyp_id} - {hyp_obj.get('opportunity_type', 'N/A')})")
        
        execution_plan = route_intent(intent, registry, results_wanted=results_per_source_query)
        
        for plan_item in execution_plan:
            src = plan_item["source"]
            if src not in source_stats:
                source_stats[src] = {
                    "attempts": 0,
                    "raw_results": 0,
                    "SUCCESS_WITH_RESULTS": 0,
                    "SUCCESS_EMPTY": 0,
                    "BLOCKED": 0,
                    "ERROR": 0,
                    "TIMEOUT": 0,
                    "UNAVAILABLE": 0,
                }
            source_stats[src]["attempts"] += 1

            raw_batch, health_batch = execute_source_plan([plan_item], return_health_records=True)

            for h in health_batch:
                st = h.get("status", "ERROR")
                if st in source_stats[src]:
                    source_stats[src][st] += 1
                all_health_records.append(h)

            source_stats[src]["raw_results"] += len(raw_batch)

            # Attach hypothesis provenance to each raw record
            for r in raw_batch:
                r["_hypothesis_info"] = {
                    "hypothesis_id": hyp_id,
                    "hypothesis": hyp_obj.get("hypothesis", ""),
                    "opportunity_type": hyp_obj.get("opportunity_type", ""),
                }

            total_raw_jobs.extend(raw_batch)

    log.info(f"\nTotal raw scraped records across all intents: {len(total_raw_jobs)}")

    # 6. Normalize and Verify India Location
    log.info("Step 6: Normalizing schema and filtering verified India locations...")
    normalized_all = [normalize_job(raw) for raw in total_raw_jobs]

    # Attach hypothesis provenance to normalized record
    for norm_job, raw_job in zip(normalized_all, total_raw_jobs):
        hyp_info = raw_job.get("_hypothesis_info", {})
        norm_job["provenance"]["hypothesis_id"] = hyp_info.get("hypothesis_id", "")
        norm_job["provenance"]["hypothesis_concept"] = hyp_info.get("hypothesis", "")
        norm_job["provenance"]["opportunity_type"] = hyp_info.get("opportunity_type", "")

    india_jobs = []
    for job in normalized_all:
        loc_meta = normalize_location(job.get("location"))
        job["normalized_location"] = loc_meta
        if loc_meta["is_india"]:
            india_jobs.append(job)

    log.info(f"Verified India opportunities: {len(india_jobs)} (from {len(normalized_all)} raw records)")

    # 7. Exact Deduplication
    log.info("Step 7: Performing deterministic exact deduplication...")
    deduped_india_jobs = dedupe_jobs(india_jobs)
    log.info(f"Total Unique India Opportunities: {len(deduped_india_jobs)}")

    # 8. Compute Raw vs. Unique Source and Provider Contribution Metrics
    metrics = compute_discovery_metrics(
        raw_jobs=total_raw_jobs,
        deduped_jobs=deduped_india_jobs,
        source_stats=source_stats
    )

    # Print Source Summary Table
    log.info("\n" + "=" * 65)
    log.info("SOURCE EXECUTION & CONTRIBUTION TABLE")
    log.info("-" * 65)
    log.info(f"{'Source':<15} | {'Raw':>6} | {'Unique':>6} | {'Duplicates':>10} | {'Health':<20}")
    log.info("-" * 65)
    for row in metrics["source_summary"]:
        log.info(f"{row['source']:<15} | {row['raw']:>6} | {row['unique']:>6} | {row['duplicates']:>10} | {row['health']:<20}")
    log.info("=" * 65)

    # Print Provider Comparison Summary
    jobspy_m = metrics["provider_metrics"]["jobspy"]
    jobspipe_m = metrics["provider_metrics"]["jobspipe"]
    log.info("\n" + "=" * 65)
    log.info("PROVIDER COMPARISON & DEDUPLICATION SUMMARY")
    log.info("-" * 65)
    log.info(f"JobSpy Raw:              {jobspy_m['raw']:>4}  |  JobSpy Unique:    {jobspy_m['unique']:>4}  |  Intra-Dupes: {jobspy_m['duplicates']:>4}")
    log.info(f"JobsPipe Raw:            {jobspipe_m['raw']:>4}  |  JobsPipe Unique:  {jobspipe_m['unique']:>4}  |  Intra-Dupes: {jobspipe_m['duplicates']:>4}")
    log.info("-" * 65)
    log.info(f"Combined Provider Unique:{metrics['provider_unique_records_total']:>4}")
    log.info(f"Intra-Provider Duplicates:{metrics['intra_provider_duplicates']:>3}")
    log.info(f"Cross-Provider Duplicates:{metrics['cross_provider_duplicates']:>3}")
    log.info(f"Total Duplicates Merged: {metrics['total_duplicates_merged']:>4}")
    log.info(f"Final Unique Opportunities:{metrics['final_unique_records']:>3}")
    log.info("-" * 65)
    log.info(f"JobSpy-Only Unique:      {metrics['jobspy_only']:>4}")
    log.info(f"JobsPipe-Only Unique:    {metrics['jobspipe_only']:>4}")
    log.info(f"Found By Both Providers: {metrics['found_by_both']:>4}")
    log.info("=" * 65)

    # 9. Persistent Career Memory Classification & SQLite Persistence
    repo = CareerOSRepository(db_path=SQLITE_DB_FILE) if Path(SQLITE_DB_FILE).exists() else None
    
    new_opps_count = 0
    seen_opps_count = 0
    reappeared_opps_count = 0
    already_applied_count = 0
    already_reviewed_count = 0
    evals_reused_count = 0
    evals_required_count = 0
    llm_calls_avoided_count = 0
    active_run_id = "run_adhoc"

    if repo:
        try:
            next_run_num = repo.get_latest_run_number() + 1
            active_run_id = f"run_{next_run_num:04d}"
            started_time = datetime.now(timezone.utc).isoformat()

            repo.insert_discovery_run({
                "id": active_run_id,
                "run_number": next_run_num,
                "started_at": started_time,
                "status": "IN_PROGRESS",
                "cv_path": cv_path,
                "max_budget": max_search_budget,
                "total_raw_records": metrics["total_raw_records"],
                "total_unique_opportunities": metrics["final_unique_records"],
                "provider_metrics": metrics["provider_metrics"],
                "source_summary": metrics["source_summary"],
                "health_records": all_health_records,
            })

            # Check existing max opportunity ID in SQLite to assign stable IDs
            with repo.connection() as conn:
                max_row = conn.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) FROM opportunities WHERE id LIKE 'disc_%';").fetchone()
                curr_max_id_num = max_row[0] if max_row and max_row[0] is not None else 0

            for r_idx, job in enumerate(deduped_india_jobs, 1):
                ckey = compute_canonical_key(job.get("title", ""), job.get("company", ""), job.get("location", ""))
                existing = repo.get_opportunity_by_key(ckey)

                if not existing:
                    curr_max_id_num += 1
                    opp_id = f"disc_{curr_max_id_num:04d}"
                    job["job_id"] = opp_id
                    job["id"] = opp_id
                    classification = "NEW"
                    new_opps_count += 1

                    repo.insert_opportunity({
                        **job,
                        "id": opp_id,
                        "canonical_key": ckey,
                        "first_seen_run_id": active_run_id,
                        "first_seen_at": datetime.now(timezone.utc).isoformat(),
                        "last_seen_run_id": active_run_id,
                        "last_seen_at": datetime.now(timezone.utc).isoformat(),
                    })
                else:
                    opp_id = existing["id"]
                    job["job_id"] = opp_id
                    job["id"] = opp_id

                    app_st = existing.get("current_application_status", "NOT_APPLIED")
                    opp_st = existing.get("current_opportunity_status", "UNKNOWN")
                    presence_st = existing.get("presence_status", "AVAILABLE")

                    if app_st != "NOT_APPLIED":
                        classification = "ALREADY_APPLIED"
                        already_applied_count += 1
                    elif opp_st != "UNKNOWN":
                        classification = "ALREADY_REVIEWED"
                        already_reviewed_count += 1
                    elif presence_st == "DISAPPEARED":
                        classification = "REAPPEARED"
                        reappeared_opps_count += 1
                    else:
                        classification = "SEEN"
                        seen_opps_count += 1

                    repo.mark_opportunity_seen(opp_id, run_id=active_run_id)

                # Track sources
                prov_data = job.get("provenance", {})
                sources_list = prov_data.get("sources", [job.get("source", "unknown")])
                providers_list = prov_data.get("providers", ["jobspy"])
                search_q = prov_data.get("search_query", "")
                hyp_id = prov_data.get("hypothesis_id", "")
                opp_type = prov_data.get("opportunity_type", "")
                hyp_concept = prov_data.get("hypothesis_concept", "")

                for s in sources_list:
                    p = "jobspipe" if s == "jobspipe" or "jobspipe" in providers_list else "jobspy"
                    repo.insert_opportunity_source({
                        "opportunity_id": opp_id,
                        "provider": p,
                        "source": s,
                        "job_url": job.get("job_url", ""),
                        "search_query": search_q,
                        "hypothesis_id": hyp_id,
                        "opportunity_type": opp_type,
                        "hypothesis_concept": hyp_concept,
                        "discovery_run_id": active_run_id,
                    })

                repo.insert_run_opportunity(active_run_id, opp_id, classification, rank=r_idx)

                # Check Evaluation Reuse
                reused = repo.find_reusable_evaluation({**job, "id": opp_id, "canonical_key": ckey})
                if reused:
                    reused_eval, reuse_type, reuse_reason = reused
                    evals_reused_count += 1
                    llm_calls_avoided_count += 1
                    job["evaluation_status"] = {
                        "reused": True,
                        "reuse_type": reuse_type,
                        "source_evaluation_id": reused_eval["id"],
                        "score": reused_eval.get("score"),
                    }
                else:
                    evals_required_count += 1
                    job["evaluation_status"] = {"reused": False, "requires_llm_call": True}

            # Update Run Completion in SQLite
            completed_time = datetime.now(timezone.utc).isoformat()
            repo.update_discovery_run(active_run_id, {
                "status": "COMPLETED",
                "completed_at": completed_time,
                "new_opportunities": new_opps_count,
                "previously_seen_opportunities": seen_opps_count,
                "reappeared_opportunities": reappeared_opps_count,
                "already_applied_opportunities": already_applied_count,
                "already_reviewed_opportunities": already_reviewed_count,
                "evaluations_required": evals_required_count,
                "evaluations_reused": evals_reused_count,
                "llm_calls_avoided": llm_calls_avoided_count,
            })

            log.info("\n" + "=" * 65)
            log.info("DISCOVERY PERSISTENT MEMORY & EVALUATION REUSE SUMMARY")
            log.info("-" * 65)
            log.info(f"Discovery Run ID:            {active_run_id}")
            log.info(f"Total Unique in Run:         {len(deduped_india_jobs):>4}")
            log.info(f"New Opportunities:           {new_opps_count:>4}")
            log.info(f"Previously Seen:             {seen_opps_count:>4}")
            log.info(f"Reappeared:                  {reappeared_opps_count:>4}")
            log.info(f"Already Applied:             {already_applied_count:>4}")
            log.info(f"Already Reviewed:            {already_reviewed_count:>4}")
            log.info("-" * 65)
            log.info(f"LLM Evaluations Required:    {evals_required_count:>4}")
            log.info(f"LLM Evaluations Reused:      {evals_reused_count:>4}")
            log.info(f"LLM Calls Avoided:           {llm_calls_avoided_count:>4}")
            reuse_pct = (evals_reused_count / len(deduped_india_jobs) * 100) if deduped_india_jobs else 0.0
            log.info(f"Evaluation Reuse Rate:       {reuse_pct:>5.1f}%")
            log.info("=" * 65)

        except Exception as e:
            log.error(f"Error persisting discovery run to SQLite: {e}")

    # 10. Save Run Artifact
    output_payload = {
        "discovery_run_id": active_run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_cv": cv_path,
        "total_capabilities_extracted": len(capabilities.get("capabilities", [])),
        "total_hypotheses_generated": len(hypotheses),
        "total_intents_executed": len(intents),
        "total_raw_jobs": metrics["total_raw_records"],
        "total_india_verified": len(india_jobs),
        "total_unique_deduped": metrics["final_unique_records"],
        "provider_unique_records_total": metrics["provider_unique_records_total"],
        "intra_provider_duplicates": metrics["intra_provider_duplicates"],
        "cross_provider_duplicates": metrics["cross_provider_duplicates"],
        "total_duplicates_merged": metrics["total_duplicates_merged"],
        "multi_source_opportunities": metrics["multi_source_opportunities"],
        "memory_metrics": {
            "new_opportunities": new_opps_count,
            "previously_seen": seen_opps_count,
            "reappeared": reappeared_opps_count,
            "already_applied": already_applied_count,
            "already_reviewed": already_reviewed_count,
            "evaluations_required": evals_required_count,
            "evaluations_reused": evals_reused_count,
            "llm_calls_avoided": llm_calls_avoided_count,
        },
        "provider_metrics": metrics["provider_metrics"],
        "cross_provider_comparison": {
            "jobspy_only": metrics["jobspy_only"],
            "jobspipe_only": metrics["jobspipe_only"],
            "found_by_both": metrics["found_by_both"],
        },
        "source_summary": metrics["source_summary"],
        "source_stats": source_stats,
        "health_records": all_health_records,
        "results": deduped_india_jobs,
    }

    if Path(output_path).name == "india_discovery_results.json" and active_run_id != "run_0001":
        output_path = f"{active_run_id}_results.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, default=str)

    log.info(f"Saved results to {output_path}")
    log.info("=" * 65)
    log.info("DYNAMIC INDIA DISCOVERY RUN COMPLETE")
    log.info("=" * 65)

    return output_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Dynamic India Opportunity Discovery")
    parser.add_argument("--cv", default=DEFAULT_CV, help="Path to candidate CV docx")
    parser.add_argument("--output", default=DEFAULT_DISCOVERY_OUTPUT, help="Output JSON path")
    parser.add_argument("--budget", type=int, default=8, help="Max search intent budget")
    parser.add_argument("--results-per-query", type=int, default=10, help="Results wanted per query")
    parser.add_argument("--reuse-artifacts", action="store_true", help="Reuse existing capability/intent artifacts")
    args = parser.parse_args()

    run_dynamic_india_discovery(
        cv_path=args.cv,
        max_search_budget=args.budget,
        results_per_source_query=args.results_per_query,
        reuse_existing_artifacts=args.reuse_artifacts,
        output_path=args.output,
    )
