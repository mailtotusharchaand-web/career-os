"""
career_os.discovery.adapters — Isolated source adapter execution.
Translates search plan items into JobSpy/API calls with strict failure isolation.
"""

import logging
from typing import Dict, Any, List, Tuple

log = logging.getLogger("career_os.discovery.adapters")


def execute_source_plan(execution_plan: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Executes a list of source plan items with strict failure isolation.
    If one source fails (e.g. LinkedIn rate limit or Naukri bot block),
    other sources execute and return results.
    
    Returns (raw_jobs_list, error_records_list).
    """
    from jobspy import scrape_jobs

    raw_jobs = []
    errors = []

    for item in execution_plan:
        source_name = item["source"]
        params = item["params"]
        intent = item.get("intent", {})

        try:
            log.info(f"Executing search on source [{source_name}] with params: {params}")
            df = scrape_jobs(
                site_name=[source_name],
                **params
            )
            records = df.to_dict("records") if (df is not None and not df.empty) else []
            for r in records:
                r["_discovered_via_source"] = source_name
                r["_search_intent"] = intent
            raw_jobs.extend(records)
            log.info(f"Source [{source_name}] returned {len(records)} raw jobs")
        except Exception as e:
            err_msg = str(e)
            log.error(f"Source [{source_name}] failed: {err_msg}")
            errors.append({
                "source": source_name,
                "intent": intent,
                "params": params,
                "error": err_msg,
            })

    return raw_jobs, errors
