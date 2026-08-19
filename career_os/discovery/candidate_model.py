"""
career_os.discovery.candidate_model — Evidence-based candidate capability extraction.
Analyzes raw CV text to produce structured, factual, transferable capability models.
"""

import json
import logging
from typing import Dict, Any, Optional

from evaluate import _llm_config, call_llm, extract_json

log = logging.getLogger("career_os.discovery.candidate_model")

CAPABILITY_EXTRACTION_PROMPT = """\
You are an expert career and capability analyst.
Your task is to analyze the candidate's CV and extract a structured, evidence-grounded capability model.

RULES:
1. Ground every extracted item SOLELY in the CV text. Do not invent experience or skills.
2. DO NOT classify capabilities into arbitrary predefined buckets or hardcoded career categories.
3. Clearly distinguish proficiency levels:
   - "demonstrated": explicitly proven through real past roles, projects, or measurable outcomes.
   - "adjacent": skills directly connected to demonstrated work that can be naturally extended.
   - "transferable": core methodological/analytical/leadership strengths that apply across industries.
   - "inferred": plausible competencies suggested by context but not explicitly measured.
4. Extract specific responsibilities, domain exposure, tools/technologies, and business problems solved.
5. Return ONLY a valid JSON object matching the schema below. No markdown outside the JSON.

SCHEMA:
{
  "candidate_summary": "<2-3 sentence factual summary of what the candidate can do based on CV>",
  "capabilities": [
    {
      "capability": "<concise capability name>",
      "evidence": ["<specific fact, metric, or project from CV supporting this>"],
      "proficiency": "demonstrated | adjacent | transferable | inferred",
      "recency": "recent | past",
      "transferable_context": "<how/where this capability creates value in other contexts>"
    }
  ],
  "responsibilities": ["<specific job responsibility/function performed>"],
  "domain_exposure": ["<business domain/industry/platform the candidate has worked in>"],
  "tools_and_technologies": ["<specific tool, software, language, or system>"],
  "business_problems_solved": ["<specific organizational/technical problem resolved>"]
}

---
CANDIDATE CV:
"""


def validate_capability_model(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates that capability model conforms to schema."""
    if not isinstance(data, dict):
        raise ValueError("Capability model must be a dictionary.")
    
    if "capabilities" not in data or not isinstance(data["capabilities"], list):
        raise ValueError("Capability model missing 'capabilities' list.")

    valid_caps = []
    for cap in data["capabilities"]:
        if isinstance(cap, dict) and "capability" in cap and "evidence" in cap:
            prof = cap.get("proficiency", "demonstrated").lower()
            if prof not in ("demonstrated", "adjacent", "transferable", "inferred"):
                prof = "demonstrated"
            cap["proficiency"] = prof
            if not isinstance(cap["evidence"], list):
                cap["evidence"] = [str(cap["evidence"])]
            valid_caps.append(cap)

    if not valid_caps:
        raise ValueError("Capability model contains zero valid capabilities.")

    data["capabilities"] = valid_caps
    data["candidate_summary"] = data.get("candidate_summary", "Candidate capability profile.")
    data["responsibilities"] = data.get("responsibilities", [])
    data["domain_exposure"] = data.get("domain_exposure", [])
    data["tools_and_technologies"] = data.get("tools_and_technologies", [])
    data["business_problems_solved"] = data.get("business_problems_solved", [])

    return data


def extract_candidate_capabilities(cv_text: str, llm_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extracts structured candidate capabilities from CV text using LLM.
    """
    config = llm_cfg or _llm_config()
    prompt = f"{CAPABILITY_EXTRACTION_PROMPT}\n{cv_text}\n"

    log.info("Invoking LLM for candidate capability extraction...")
    response_text = call_llm(prompt, config)
    raw_data = extract_json(response_text)
    validated = validate_capability_model(raw_data)
    log.info(f"Successfully extracted {len(validated['capabilities'])} capabilities.")
    return validated
