"""
career_os.discovery.normalizer — Canonical schema mapping and deterministic exact deduplication.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return "" if val != val else str(val)  # NaN check
    return str(val).strip()


def normalize_job(raw: Dict[str, Any], query_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Maps raw scraper records to canonical Career OS opportunity schema with provenance.
    """
    ctx = query_context or {}
    source_name = _safe_str(raw.get("site") or raw.get("_discovered_via_source") or "unknown")
    search_query = _safe_str(ctx.get("search_query") or (raw.get("_search_intent") or {}).get("search_query") or "")

    return {
        "title": _safe_str(raw.get("title", "")),
        "company": _safe_str(raw.get("company", "")),
        "location": _safe_str(raw.get("location", "")),
        "description": _safe_str(raw.get("description", "")),
        "job_url": _safe_str(raw.get("job_url", "")),
        "source": source_name,
        "date_posted": _safe_str(raw.get("date_posted", "")),
        "job_type": _safe_str(raw.get("job_type", "")),
        "salary_min": raw.get("min_amount"),
        "salary_max": raw.get("max_amount"),
        "salary_interval": _safe_str(raw.get("interval", "")),
        "is_remote": bool(raw.get("is_remote", False)),
        "provenance": {
            "sources": [source_name] if source_name else [],
            "search_query": search_query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
    }


def dedupe_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicates opportunities based on exact canonical key: (title, company, location).
    Merges sources, keeps earliest date_posted, and preserves longest description.
    """
    seen: Dict[tuple, Dict[str, Any]] = {}

    for j in jobs:
        title = j.get("title", "").strip().lower()
        company = j.get("company", "").strip().lower()
        location = j.get("location", "").strip().lower()
        
        key = (title, company, location)

        if key not in seen:
            seen[key] = j
        else:
            existing = seen[key]
            # Merge sources list in provenance
            for s in j.get("provenance", {}).get("sources", []):
                if s and s not in existing.get("provenance", {}).get("sources", []):
                    existing["provenance"]["sources"].append(s)

            # Preserve earliest date_posted
            if j.get("date_posted") and (not existing.get("date_posted") or j["date_posted"] < existing["date_posted"]):
                existing["date_posted"] = j["date_posted"]

            # Preserve longest description
            if len(j.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = j["description"]

            # Preserve salary if missing in existing
            if not existing.get("salary_min") and j.get("salary_min"):
                existing["salary_min"] = j["salary_min"]
                existing["salary_max"] = j.get("salary_max")
                existing["salary_interval"] = j.get("salary_interval")

            # Preserve URL if missing in existing
            if not existing.get("job_url") and j.get("job_url"):
                existing["job_url"] = j["job_url"]

    return list(seen.values())
