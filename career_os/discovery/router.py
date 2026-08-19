"""
career_os.discovery.router — Capability-based source router.
Matches search intent requirements to source capabilities with ZERO career logic.
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def load_source_registry(config_path: str = "config/sources.json") -> Dict[str, Any]:
    """Loads source capabilities configuration."""
    path = Path(config_path)
    if not path.exists():
        return {"sources": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def route_intent(intent: Dict[str, Any], registry: Dict[str, Any], results_wanted: int = 10, hours_old: int = 168) -> List[Dict[str, Any]]:
    """
    Translates a generic SearchIntent into source-specific execution plans based on source capabilities.
    """
    search_query = intent.get("search_query", "")
    country_code = intent.get("country_code", "IN")
    location_intent = intent.get("location_intent", "India")
    
    sources_config = registry.get("sources", {})
    execution_plan = []

    for source_name, source_meta in sources_config.items():
        if not source_meta.get("enabled", False):
            continue

        coverage = source_meta.get("geographic_coverage", [])
        if country_code not in coverage and "global" not in coverage:
            continue

        params: Dict[str, Any] = {
            "search_term": search_query,
            "results_wanted": results_wanted,
            "hours_old": hours_old,
        }

        # Handle country parameter if source supports it (e.g. Indeed country_indeed='india')
        if source_meta.get("supports_country_param", False):
            country_map = source_meta.get("country_code_map", {})
            mapped_country = country_map.get(country_code, country_code.lower())
            params["country_indeed"] = mapped_country

        # Handle location parameter if source supports it (e.g. LinkedIn location='India')
        if source_meta.get("supports_location_param", False):
            if location_intent and not source_meta.get("supports_country_param", False):
                params["location"] = location_intent

        execution_plan.append({
            "source": source_name,
            "intent": intent,
            "params": params,
        })

    return execution_plan
