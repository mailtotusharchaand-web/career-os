#!/usr/bin/env python3
"""
discover_india.py — Dynamic India Opportunity Discovery for Career OS.

Pipeline:
1. Parse CV (Tushar_Chaand_CV.docx)
2. Extract Candidate Capabilities -> candidate_capabilities.json
3. Generate Opportunity Hypotheses -> opportunity_hypotheses.json
4. Generate Dynamic Search Intents -> search_intents.json
5. Route and Execute across India sources (Indeed, Naukri, LinkedIn)
6. Normalize, Verify India location, and Deduplicate -> india_discovery_results.json
"""

import json
import logging
import sys
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("discover_india")

DEFAULT_CV = "Tushar_Chaand_CV.docx"
CAPABILITIES_OUTPUT = "candidate_capabilities.json"
HYPOTHESES_OUTPUT = "opportunity_hypotheses.json"
INTENTS_OUTPUT = "search_intents.json"
DISCOVERY_OUTPUT = "india_discovery_results.json"


def run_dynamic_india_discovery(
    cv_path: str = DEFAULT_CV,
    max_search_budget: int = 8,
    results_per_source_query: int = 10,
    reuse_existing_artifacts: bool = False
) -> Dict[str, Any]:
    """
    Orchestrates the dynamic CV-driven opportunity discovery pipeline for India.
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
    all_errors = []
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
                source_stats[src] = {"attempts": 0, "successes": 0, "failures": 0, "raw_results": 0}
            source_stats[src]["attempts"] += 1

            raw_batch, err_batch = execute_source_plan([plan_item])

            if err_batch:
                source_stats[src]["failures"] += 1
                all_errors.extend(err_batch)
            else:
                source_stats[src]["successes"] += 1
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

    # 8. Save Artifacts
    output_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_cv": cv_path,
        "total_capabilities_extracted": len(capabilities.get("capabilities", [])),
        "total_hypotheses_generated": len(hypotheses),
        "total_intents_executed": len(intents),
        "total_raw_jobs": len(total_raw_jobs),
        "total_india_verified": len(india_jobs),
        "total_unique_deduped": len(deduped_india_jobs),
        "source_stats": source_stats,
        "errors": all_errors,
        "results": deduped_india_jobs,
    }

    with open(DISCOVERY_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, default=str)

    log.info(f"Saved results to {DISCOVERY_OUTPUT}")
    log.info("=" * 65)
    log.info("DYNAMIC INDIA DISCOVERY RUN COMPLETE")
    log.info("=" * 65)

    return output_payload


if __name__ == "__main__":
    run_dynamic_india_discovery()
