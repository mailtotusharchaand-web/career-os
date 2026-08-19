"""
career_os.discovery.intents — Dynamic search intent generation and query expansion.
Translates opportunity hypotheses into realistic job-search terminology for India sources.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from evaluate import _llm_config, call_llm, extract_json

log = logging.getLogger("career_os.discovery.intents")

INTENT_GENERATION_PROMPT = """\
You are an expert talent search and query formulation specialist for the Indian job market.
Your task is to convert the candidate's opportunity hypotheses into concrete, effective job search queries.

RULES:
1. Generate realistic, market-standard search terminology that real hiring managers and job boards use in India.
2. Formulate 1 to 3 distinct search query variants per hypothesis to capture different market vocabularies for the same capability.
3. AVOID:
   - Overly generic keywords (e.g., "Manager", "Analyst", "Lead" without context).
   - Keyword soup or pasting full sentences from the CV.
   - Restricting searches to narrow fixed titles if multiple job formulations exist.
4. GEOGRAPHY CONSTRAINT (CRITICAL):
   - All search intents MUST strictly target India (country_code = "IN", location_intent = "India").
   - DO NOT generate international search queries (US, UK, Europe, etc.).
5. Return ONLY a valid JSON array of search intent objects matching the schema below. No markdown outside JSON.

SCHEMA:
[
  {
    "search_query": "<concise, high-precision job search query string, 2-4 words>",
    "country_code": "IN",
    "location_intent": "India",
    "hypothesis_id": "<matching hypothesis_id, e.g. hyp_001>",
    "rationale": "<brief explanation of market terminology chosen>"
  }
]
"""


def dedupe_intents(intents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicates search intents by normalized query string."""
    seen = set()
    deduped = []
    for intent in intents:
        query_norm = intent.get("search_query", "").strip().lower()
        if query_norm and query_norm not in seen:
            seen.add(query_norm)
            deduped.append(intent)
    return deduped


def validate_and_filter_intents(data: Any, max_budget: int = 15) -> List[Dict[str, Any]]:
    """
    Validates, filters (India-only enforcement), and budget-limits search intents.
    """
    if not isinstance(data, list):
        if isinstance(data, dict) and "intents" in data and isinstance(data["intents"], list):
            data = data["intents"]
        else:
            raise ValueError("Search intents must be a list.")

    valid_intents = []
    for item in data:
        if not isinstance(item, dict):
            continue

        query = str(item.get("search_query", "")).strip()
        if not query or len(query) < 3:
            continue

        # Enforce India-only constraint for Phase 1
        country = str(item.get("country_code", "IN")).strip().upper()
        if country != "IN":
            log.warning(f"Rejecting non-India search intent: '{query}' (country_code: {country})")
            continue

        valid_intents.append({
            "search_query": query,
            "country_code": "IN",
            "location_intent": "India",
            "hypothesis_id": str(item.get("hypothesis_id", "unknown")).strip(),
            "rationale": str(item.get("rationale", "")).strip(),
        })

    # Deduplicate
    deduped = dedupe_intents(valid_intents)

    # Apply execution budget guardrail
    if len(deduped) > max_budget:
        log.info(f"Capping search intents at execution budget limit: {max_budget} (from {len(deduped)})")
        deduped = deduped[:max_budget]

    if not deduped:
        raise ValueError("No valid India search intents generated.")

    return deduped


def generate_search_intents(
    hypotheses: List[Dict[str, Any]],
    max_budget: int = 15,
    llm_cfg: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Generates dynamic search intents from opportunity hypotheses using LLM.
    """
    config = llm_cfg or _llm_config()
    hyp_str = json.dumps(hypotheses, indent=2)
    prompt = (
        f"{INTENT_GENERATION_PROMPT}\n"
        f"---\nOPPORTUNITY HYPOTHESES:\n{hyp_str}\n"
    )

    log.info("Invoking LLM for search intent generation...")
    response_text = call_llm(prompt, config)
    raw_data = extract_json(response_text)
    validated = validate_and_filter_intents(raw_data, max_budget=max_budget)
    log.info(f"Successfully generated {len(validated)} validated India search intents.")
    return validated
