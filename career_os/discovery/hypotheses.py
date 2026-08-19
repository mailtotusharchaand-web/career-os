"""
career_os.discovery.hypotheses — Open-world opportunity hypotheses generation.
Explores plausible career and market opportunity spaces grounded in candidate capabilities.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from evaluate import _llm_config, call_llm, extract_json

log = logging.getLogger("career_os.discovery.hypotheses")

HYPOTHESIS_GENERATION_PROMPT = """\
You are an open-world career opportunity strategist.
Your task is to analyze the candidate's capability model and generate diverse, evidence-grounded opportunity hypotheses.

RULES:
1. Ground every hypothesis in the candidate's actual capabilities and evidence.
2. DO NOT restrict hypotheses to a single narrow job title or hardcoded industry.
3. Explore the full space of plausible opportunities:
   - "direct": natural continuation of primary past roles and platforms.
   - "adjacent": similar core functions applied to related domains or platforms.
   - "transferable": different functional areas where the candidate's analytical/operational toolkit creates high value.
   - "unexpected": non-obvious fits where an unusual combination of skills provides a competitive advantage.
   - "stretch": higher-scope or emerging opportunities feasible with targeted upskilling.
4. Do NOT force a fixed count or percentage of each type. Generate only hypotheses supported by evidence.
5. Return ONLY a valid JSON array of hypothesis objects matching the schema below. No markdown outside JSON.

SCHEMA:
[
  {
    "hypothesis_id": "hyp_001",
    "hypothesis": "<clear statement of the opportunity concept / target capability area>",
    "rationale": "<2-3 sentences explaining why this candidate is a strong fit for this opportunity space>",
    "supporting_capabilities": ["<exact capability names from candidate model>"],
    "evidence": "<specific evidence from CV supporting this hypothesis>",
    "opportunity_type": "direct | adjacent | transferable | unexpected | stretch"
  }
]
"""


def validate_hypotheses(data: Any) -> List[Dict[str, Any]]:
    """Validates list of opportunity hypotheses."""
    if not isinstance(data, list):
        if isinstance(data, dict) and "hypotheses" in data and isinstance(data["hypotheses"], list):
            data = data["hypotheses"]
        else:
            raise ValueError("Opportunity hypotheses must be a list.")

    valid_hypotheses = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        if "hypothesis" not in item or not item.get("hypothesis"):
            continue

        hyp_id = item.get("hypothesis_id") or f"hyp_{idx+1:03d}"
        opp_type = item.get("opportunity_type", "adjacent").lower()
        if opp_type not in ("direct", "adjacent", "transferable", "unexpected", "stretch"):
            opp_type = "adjacent"

        supp_caps = item.get("supporting_capabilities", [])
        if not isinstance(supp_caps, list):
            supp_caps = [str(supp_caps)]

        valid_hypotheses.append({
            "hypothesis_id": hyp_id,
            "hypothesis": str(item["hypothesis"]).strip(),
            "rationale": str(item.get("rationale", "")).strip(),
            "supporting_capabilities": supp_caps,
            "evidence": str(item.get("evidence", "")).strip(),
            "opportunity_type": opp_type,
        })

    if not valid_hypotheses:
        raise ValueError("No valid opportunity hypotheses found in LLM output.")

    return valid_hypotheses


def generate_opportunity_hypotheses(
    capabilities_model: Dict[str, Any],
    objective: Optional[Dict[str, Any]] = None,
    llm_cfg: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Generates dynamic opportunity hypotheses from candidate capabilities using LLM.
    """
    config = llm_cfg or _llm_config()
    caps_str = json.dumps(capabilities_model, indent=2)
    obj_str = f"\nUSER OBJECTIVE:\n{json.dumps(objective, indent=2)}\n" if objective else ""

    prompt = (
        f"{HYPOTHESIS_GENERATION_PROMPT}\n"
        f"---\nCANDIDATE CAPABILITY MODEL:\n{caps_str}\n"
        f"{obj_str}"
    )

    log.info("Invoking LLM for opportunity hypotheses generation...")
    response_text = call_llm(prompt, config)
    raw_data = extract_json(response_text)
    validated = validate_hypotheses(raw_data)
    log.info(f"Successfully generated {len(validated)} opportunity hypotheses.")
    return validated
