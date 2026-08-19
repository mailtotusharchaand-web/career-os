#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evaluate.py — LLM-driven job evaluation for Career OS

Architecture principle:
  The LLM decides what constitutes a suitable opportunity.
  Deterministic gates enforce ONLY explicit candidate constraints
  (employment type, recency). Nothing else blocks a job from
  reaching the LLM.

Pipeline:
  1. Parse CV via MarkItDown → raw text
  2. Load jobs JSON
  3. Apply ONLY explicit candidate constraint gates (employment type, recency)
  4. For each job that passes: call LLM with full CV + job description
  5. LLM returns structured JSON — no keyword scoring, no domain lists
  6. Save results incrementally (interrupted runs lose nothing)
  7. Print ranked summary

LLM Provider configuration (environment variables):
  LLM_PROVIDER   = "gemini" | "openai"   (default: gemini)
  LLM_API_KEY    = your API key           (required)
  LLM_MODEL      = model name             (default: gemini-2.5-flash)
  LLM_BASE_URL   = override base URL      (optional, for OpenAI-compatible APIs)

Usage:
  python evaluate.py [--jobs tier1_jobs.json] [--cv Tushar_Chaand_CV.docx]
                     [--output llm_evaluations.json] [--sample N] [--all]
                     [--skip-gates] [--model MODEL]
"""

import json
import os
import sys
import time
import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

# Force UTF-8 output on Windows so special characters print correctly.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 0. CONSTANTS
# ---------------------------------------------------------------------------

DEFAULT_JOBS_FILE = "tier1_jobs.json"
DEFAULT_CV_FILE = "Tushar_Chaand_CV.docx"
DEFAULT_OUTPUT_FILE = "llm_evaluations.json"
DEFAULT_SAMPLE = 5            # Safety default — never process all without --all
MAX_JD_CHARS = 3500           # Trim long job descriptions to control token cost
MAX_CV_CHARS = 6000           # Full CV is short; this is a safety ceiling
RETRY_ATTEMPTS = 4            # More retries for transient 503s
RETRY_DELAY_SECONDS = 20      # Base delay — doubles each retry (20s, 40s, 80s)
INTER_CALL_PAUSE = 4          # Seconds between LLM calls — free tier rate limiting

# Explicit candidate employment constraints (the ONLY domain-free hard filters)
# These represent genuine "I won't do this" constraints, not opportunity assumptions.
EXCLUDED_EMPLOYMENT_TITLE_KEYWORDS = [
    "intern", "internship", "trainee", "co-op", "coop", "apprentice",
    "part-time", "part time", "summer intern", "winter intern", "fellowship",
]
EXCLUDED_EMPLOYMENT_TYPE_VALUES = [
    "internship", "part-time", "part_time", "parttime", "temporary",
]
MAX_JOB_AGE_DAYS = 30  # Recency constraint — older postings are not actionable


# ---------------------------------------------------------------------------
# 1. CV PARSING — markitdown
# ---------------------------------------------------------------------------

def parse_cv(cv_path: str) -> str:
    """
    Parse CV from DOCX (or PDF) to plain text using MarkItDown.
    Returns raw text. Raises on failure.
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise SystemExit("markitdown not installed. Run: pip install markitdown")

    md = MarkItDown()
    result = md.convert(cv_path)
    text = result.text_content.strip()
    if not text:
        raise ValueError(f"MarkItDown returned empty text for {cv_path}")
    return text[:MAX_CV_CHARS]


# ---------------------------------------------------------------------------
# 2. JOB LOADING
# ---------------------------------------------------------------------------

def load_jobs(jobs_path: str) -> list:
    """Load and normalize jobs from JSON. Add job_id if missing."""
    with open(jobs_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "results" in data:
        jobs = data["results"]
        is_discovery = True
    elif isinstance(data, list):
        jobs = data
        is_discovery = False
    else:
        jobs = []
        is_discovery = False

    for i, job in enumerate(jobs):
        if "job_id" not in job:
            if is_discovery:
                job["job_id"] = f"disc_{i + 1:04d}"
            else:
                job["job_id"] = f"job_{i:04d}"
        if is_discovery and "discovery_id" not in job:
            job["discovery_id"] = job["job_id"]
        # Sanitize NaN salaries (pandas serialization artifact)
        for salary_field in ("salary_min", "salary_max"):
            val = job.get(salary_field)
            if val is not None:
                try:
                    if val != val:   # NaN check
                        job[salary_field] = None
                except TypeError:
                    pass
    return jobs


# ---------------------------------------------------------------------------
# 3. EXPLICIT CANDIDATE CONSTRAINT GATES
#
# These are the ONLY hard pre-LLM filters in this file.
#
# What is NOT a gate here:
#   - Role type (product vs non-product) — LLM decides relevance
#   - Domain (payments vs trading vs healthcare) — LLM decides relevance
#   - Company — LLM decides relevance
#   - Seniority — LLM assesses fit, not a binary gate
#   - Location preference — LLM notes it; candidate can filter post-evaluation
#   - PRIMARY_DOMAINS or any domain list — not used anywhere in this file
#
# What IS a gate here:
#   - Employment type: "I only want full-time or contract" (explicit constraint)
#   - Recency: "I only want jobs posted in the last 30 days" (explicit constraint)
# ---------------------------------------------------------------------------

def _gate_employment_type(job: dict) -> tuple:
    """
    Reject internships, part-time, and temporary roles.
    Constraint source: candidate explicitly does not want these.
    Returns (passes: bool, reason: str)
    """
    title_lower = job.get("title", "").lower()
    job_type_lower = (job.get("job_type") or "").lower()

    for kw in EXCLUDED_EMPLOYMENT_TITLE_KEYWORDS:
        if kw in title_lower:
            return False, f"employment_type: excluded keyword in title: '{kw}'"

    for val in EXCLUDED_EMPLOYMENT_TYPE_VALUES:
        if val in job_type_lower:
            return False, f"employment_type: excluded job_type value: '{val}'"

    return True, "employment_type: acceptable"


def _gate_recency(job: dict) -> tuple:
    """
    Reject jobs posted more than MAX_JOB_AGE_DAYS days ago.
    Unknown dates pass (benefit of the doubt).
    Returns (passes: bool, reason: str)
    """
    date_str = job.get("date_posted", "")
    if not date_str:
        return True, "recency: date unknown — not penalised"

    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                posted = datetime.strptime(date_str[:19], fmt[:19])
                break
            except ValueError:
                continue
        else:
            return True, f"recency: unrecognised date format '{date_str}' — not penalised"

        days_old = (datetime.now() - posted).days
        if days_old > MAX_JOB_AGE_DAYS:
            return False, f"recency: posted {days_old} days ago (limit: {MAX_JOB_AGE_DAYS})"
        return True, f"recency: posted {days_old} days ago — OK"
    except Exception as e:
        return True, f"recency: date parse error ({e}) — not penalised"


def run_explicit_constraint_gates(job: dict) -> tuple:
    """
    Run the two explicit candidate constraint gates.
    Returns (all_passed: bool, passed: list[str], failed: list[str])

    These gates enforce only what the candidate explicitly said they don't want.
    They do NOT filter by domain, role type, company, or seniority.
    """
    passed, failed = [], []

    for gate_fn in (_gate_employment_type, _gate_recency):
        ok, reason = gate_fn(job)
        (passed if ok else failed).append(reason)

    return len(failed) == 0, passed, failed


# ---------------------------------------------------------------------------
# 4. LLM CLIENT
# ---------------------------------------------------------------------------

def load_dotenv(path: str = ".env") -> None:
    """Load key-value pairs from .env file into os.environ if not already set or empty."""
    env_file = Path(path)
    if not env_file.exists():
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if val and not os.environ.get(key):
                        os.environ[key] = val
    except Exception:
        pass


def _llm_config() -> dict:
    """Read LLM configuration from environment variables or .env file."""
    load_dotenv()
    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    api_key  = os.environ.get("LLM_API_KEY", "")
    model    = os.environ.get("LLM_MODEL", "")
    base_url = os.environ.get("LLM_BASE_URL", "")

    if not api_key:
        raise SystemExit(
            "LLM_API_KEY environment variable not set.\n"
            "Set LLM_API_KEY in the local .env file or environment."
        )

    if provider == "gemini":
        return {
            "provider": "gemini",
            "api_key": api_key,
            "model": model or "gemini-flash-lite-latest",
            "base_url": base_url or "https://generativelanguage.googleapis.com/v1beta",
        }
    elif provider in ("openai", "openai_compatible"):
        return {
            "provider": "openai",
            "api_key": api_key,
            "model": model or "gemini-flash-lite-latest",
            "base_url": base_url or "https://api.openai.com/v1",
        }
    else:
        raise SystemExit(f"Unknown LLM_PROVIDER: {provider!r}. Use 'gemini' or 'openai'.")


def _call_gemini(prompt: str, config: dict) -> str:
    """Call Gemini REST API. Returns raw response text."""
    import requests
    url = (
        f"{config['base_url']}/models/{config['model']}:generateContent"
        f"?key={config['api_key']}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": 2048,
        },
    }
    try:
        r = requests.post(url, json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        err_str = str(e)
        if config.get("api_key") and config["api_key"] in err_str:
            err_str = err_str.replace(config["api_key"], "[REDACTED]")
        raise RuntimeError(err_str) from None


def _call_openai(prompt: str, config: dict) -> str:
    """Call OpenAI-compatible REST API. Returns raw response text."""
    import requests
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "system",
                "content": "You are a precise career evaluation assistant. Always respond with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.15,
        "max_tokens": 2048,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=90)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        err_str = str(e)
        if config.get("api_key") and config["api_key"] in err_str:
            err_str = err_str.replace(config["api_key"], "[REDACTED]")
        raise RuntimeError(err_str) from None


def call_llm(prompt: str, config: dict) -> str:
    """Dispatch to the correct provider with exponential backoff retry."""
    provider = config["provider"]
    last_error = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            if provider == "gemini":
                return _call_gemini(prompt, config)
            else:
                return _call_openai(prompt, config)
        except Exception as e:
            last_error = e
            if attempt < RETRY_ATTEMPTS:
                # Exponential backoff: 20s, 40s, 80s
                wait = RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                err_type = type(e).__name__
                print(f"    [retry {attempt}/{RETRY_ATTEMPTS}] LLM error: {err_type}. Waiting {wait}s...")
                time.sleep(wait)

    err_msg = str(last_error)
    if config.get("api_key") and config["api_key"] in err_msg:
        err_msg = err_msg.replace(config["api_key"], "[REDACTED]")
    raise RuntimeError(f"LLM call failed after {RETRY_ATTEMPTS} attempts: {err_msg}")


# ---------------------------------------------------------------------------
# 5. PROMPT CONSTRUCTION
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a rigorous, unbiased career evaluation expert.

Your task is to evaluate whether a job opportunity is genuinely suitable
for this specific candidate, based SOLELY on their actual CV.

RULES — READ CAREFULLY:

1. Ground every assessment in the CV. Do NOT invent experience, skills, or
   credentials the candidate does not have.

2. Distinguish clearly between:
   (a) CURRENT EXPERIENCE: roles, projects, outcomes the candidate already has.
   (b) TRANSFERABLE CAPABILITIES: skills/methods that work in a new context.
   (c) MISSING CRITICAL SKILLS: what the job needs that the CV lacks.
   (d) PLAUSIBLE TRANSITION: adjacent move the candidate's background supports.
   (e) UNREALISTIC LEAP: requires expertise clearly absent from the CV.

3. Do NOT reject a role purely because it is in an unfamiliar domain.
   Evaluate whether the candidate's capabilities transfer.

4. Do NOT recommend a role purely because the salary or prestige is high.
   High upside + missing critical skills = Long Shot, not Strong Apply.

5. Use UNKNOWN when required information is absent from either the CV
   or the job description. Do not guess or hallucinate facts.

6. Return ONLY a JSON object. No markdown. No prose outside the JSON.\
"""

EVALUATION_SCHEMA = """\
Return exactly this JSON object (all fields required):

{
  "role_fit": <integer 0-100>,
  "current_experience_fit": <integer 0-100>,
  "transferable_capability_fit": <integer 0-100>,
  "seniority_fit": <integer 0-100>,
  "opportunity_alignment": <integer 0-100>,
  "transition_difficulty": "low" | "medium" | "high" | "very_high",
  "missing_critical_skills": [<string>, ...],
  "key_strengths": [<string>, ...],
  "career_upside": "low" | "medium" | "high",
  "compensation_upside": "unknown" | "low" | "medium" | "high",
  "probability_of_obtaining": <integer 0-100>,
  "confidence": "high" | "medium" | "low",
  "recommendation": "Strong Apply" | "Apply" | "Consider" | "Long Shot" | "Skip",
  "reasoning": "<2-4 sentences — no bullet lists>",
  "evidence": "<specific CV facts that support or challenge the fit>",
  "missing_evidence": "<information absent from CV or JD that would change the assessment>",
  "overall_score": <integer 0-100>
}

Scoring guidance:
- role_fit: Does this role match the candidate's function/track (not just domain)?
- current_experience_fit: How directly does their existing CV experience map to THIS role?
- transferable_capability_fit: How much of their toolkit transfers even if domain is new?
- seniority_fit: Is the seniority level appropriate for someone with this background?
- opportunity_alignment: Does this role advance the candidate's career in a realistic direction?
- transition_difficulty: How hard is it to move from CV → this role?
- probability_of_obtaining: Realistic competitive probability. Discount for missing skills,
  visa/sponsorship complexity, location mismatch, and market competition.
- overall_score: Holistic judgment. Weight role_fit and probability_of_obtaining heavily.
  A role can score 70+ even if it requires a moderate transition, provided the candidate's
  capabilities genuinely transfer. A role with missing critical technical skills should
  not exceed 50 in overall_score regardless of domain appeal.\
"""


def build_prompt(cv_text: str, job: dict) -> str:
    """Build the evaluation prompt for a single job."""
    title    = job.get("title", "UNKNOWN")
    company  = job.get("company", "UNKNOWN")
    location = job.get("location", "UNKNOWN")
    is_remote   = job.get("is_remote", False)
    job_type    = job.get("job_type", "")
    salary_min  = job.get("salary_min")
    salary_max  = job.get("salary_max")
    salary_int  = job.get("salary_interval", "")
    description = (job.get("description") or "")[:MAX_JD_CHARS]

    if salary_min and salary_max:
        salary_str = f"${salary_min:,.0f}–${salary_max:,.0f} {salary_int}".strip()
    elif salary_min:
        salary_str = f"${salary_min:,.0f}+ {salary_int}".strip()
    else:
        salary_str = "Not disclosed"

    work_mode = "Remote" if is_remote else f"On-site/Hybrid ({location})"

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"---\nCANDIDATE CV:\n{cv_text}\n\n"
        f"---\nJOB TO EVALUATE:\n"
        f"Title:           {title}\n"
        f"Company:         {company}\n"
        f"Location:        {location}\n"
        f"Work mode:       {work_mode}\n"
        f"Employment type: {job_type or 'Not specified'}\n"
        f"Compensation:    {salary_str}\n\n"
        f"Job Description:\n{description if description else '[No description available]'}\n\n"
        f"---\nEVALUATION TASK:\n"
        f"Evaluate this job opportunity for this candidate.\n"
        f"{EVALUATION_SCHEMA}\n"
    )


# ---------------------------------------------------------------------------
# 6. RESPONSE PARSING
# ---------------------------------------------------------------------------

def extract_json(raw: str) -> dict:
    """
    Extract JSON object from LLM response.
    Handles: markdown fences, leading prose, trailing text.
    Raises ValueError if no valid JSON found.
    """
    # Strip ```json ... ``` fences
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.replace("```", "").strip()

    # Direct parse attempt
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract first { ... } block
    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in LLM response:\n{raw[:400]}")


def validate_evaluation(data: dict) -> dict:
    """
    Validate and clamp LLM output.
    Fills missing fields with safe defaults rather than crashing.
    """
    int_fields = [
        "role_fit", "current_experience_fit", "transferable_capability_fit",
        "seniority_fit", "opportunity_alignment", "probability_of_obtaining",
        "overall_score",
    ]
    for f in int_fields:
        val = data.get(f)
        if val is None:
            data[f] = 0
        else:
            try:
                data[f] = max(0, min(100, int(val)))
            except (TypeError, ValueError):
                data[f] = 0

    str_defaults = {
        "transition_difficulty": "medium",
        "career_upside":         "unknown",
        "compensation_upside":   "unknown",
        "confidence":            "low",
        "recommendation":        "Consider",
        "reasoning":             "UNKNOWN",
        "evidence":              "UNKNOWN",
        "missing_evidence":      "UNKNOWN",
    }
    for f, default in str_defaults.items():
        if not data.get(f):
            data[f] = default

    for f in ("missing_critical_skills", "key_strengths"):
        if not isinstance(data.get(f), list):
            data[f] = []

    return data


# ---------------------------------------------------------------------------
# 7. INCREMENTAL SAVE / LOAD
# ---------------------------------------------------------------------------

def load_existing_results(output_path: str) -> dict:
    """
    Load previously completed evaluations keyed by job_id.
    IMPORTANT: Only loads successfully evaluated jobs (not error results).
    Error results are excluded so they get retried on the next run.
    Gate-rejected jobs ARE loaded (they don't need retrying).
    """
    if not Path(output_path).exists():
        return {}
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("evaluations", [])
        resumable = {}
        for r in results:
            if "job_id" not in r:
                continue
            # Gate-rejected: always resume (no LLM call needed)
            if r.get("gate_failed"):
                resumable[r["job_id"]] = r
                continue
            # LLM evaluated: only resume if no error
            ev = r.get("llm_evaluation") or {}
            if ev and "_error" not in ev:
                resumable[r["job_id"]] = r
        return resumable
    except Exception as e:
        print(f"[warn] Could not load existing results from {output_path}: {e}")
        return {}


def save_results(results: list, output_path: str, meta: dict) -> None:
    """Atomically overwrite output file with all results so far."""
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta,
        "evaluations": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# 8. DISPLAY
# ---------------------------------------------------------------------------

RECOMMENDATION_ORDER = {
    "Strong Apply": 0,
    "Apply":        1,
    "Consider":     2,
    "Long Shot":    3,
    "Skip":         4,
}


def print_summary(results: list) -> None:
    """Print ranked summary to stdout."""
    llm_evaluated = [r for r in results if not r.get("gate_failed") and r.get("llm_evaluation")]
    gate_rejected  = [r for r in results if r.get("gate_failed")]

    scored = sorted(
        llm_evaluated,
        key=lambda r: (
            RECOMMENDATION_ORDER.get(
                r.get("llm_evaluation", {}).get("recommendation", "Skip"), 99
            ),
            -(r.get("llm_evaluation", {}).get("overall_score") or 0),
        ),
    )

    print("\n" + "=" * 72)
    print("LLM EVALUATION RESULTS - ranked by recommendation then score")
    print("=" * 72)

    for i, r in enumerate(scored, 1):
        ev      = r.get("llm_evaluation", {})
        rec     = ev.get("recommendation", "?")
        score   = ev.get("overall_score", 0)
        prob    = ev.get("probability_of_obtaining", 0)
        upside  = ev.get("career_upside", "?")
        diff    = ev.get("transition_difficulty", "?")
        conf    = ev.get("confidence", "?")
        title   = r.get("title", "")[:55]
        company = r.get("company", "")[:28]
        loc     = r.get("location", "")[:30]
        url     = r.get("application_url", "")

        print(f"\n{i:>2}. [{rec}]  score={score}  P(get)={prob}%  upside={upside}  difficulty={diff}  confidence={conf}")
        print(f"    {title}")
        print(f"    {company} - {loc}")
        print(f"    {url}")

        strengths = ev.get("key_strengths", [])
        missing   = ev.get("missing_critical_skills", [])
        if strengths:
            print(f"    STRENGTHS: {' | '.join(strengths[:4])}")
        if missing:
            print(f"    MISSING:   {' | '.join(missing[:4])}")

        reasoning = ev.get("reasoning", "")
        if reasoning and reasoning != "UNKNOWN":
            print(f"    REASONING: {reasoning}")

        evidence = ev.get("evidence", "")
        if evidence and evidence != "UNKNOWN":
            print(f"    EVIDENCE:  {evidence}")

    if gate_rejected:
        print(f"\n[{len(gate_rejected)} job(s) rejected by explicit constraint gates before LLM]")
        for r in gate_rejected:
            print(f"   - {r['title'][:55]}  ->  {r.get('gate_failure_reasons', [])}")

    # Distribution summary
    counts = {}
    for r in llm_evaluated:
        rec = r.get("llm_evaluation", {}).get("recommendation", "Skip")
        counts[rec] = counts.get(rec, 0) + 1

    print("\n" + "-" * 72)
    print("DISTRIBUTION:")
    for label in ["Strong Apply", "Apply", "Consider", "Long Shot", "Skip"]:
        n = counts.get(label, 0)
        if n:
            print(f"  {label}: {n}")


# ---------------------------------------------------------------------------
# 9. MAIN
# ---------------------------------------------------------------------------

def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(
        description="LLM-driven job evaluation - Career OS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables:\n"
            "  LLM_PROVIDER   gemini | openai  (default: gemini)\n"
            "  LLM_API_KEY    required\n"
            "  LLM_MODEL      model name       (default: gemini-flash-latest)\n"
            "  LLM_BASE_URL   custom base URL  (optional)\n"
        ),
    )
    parser.add_argument("--jobs",   default=DEFAULT_JOBS_FILE, help="Jobs JSON file")
    parser.add_argument("--cv",     default=DEFAULT_CV_FILE,   help="CV file (DOCX or PDF)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE, help="Output JSON file")
    parser.add_argument(
        "--sample", type=int, default=DEFAULT_SAMPLE,
        help=f"Evaluate only the first N jobs (default: {DEFAULT_SAMPLE}). Use --all to ignore this.",
    )
    parser.add_argument("--all",        action="store_true", help="Evaluate all jobs (overrides --sample)")
    parser.add_argument("--skip-gates", action="store_true", help="Skip even the employment-type/recency gates")
    parser.add_argument("--model",      default="", help="Override LLM model name")
    args = parser.parse_args()

    if args.model:
        os.environ["LLM_MODEL"] = args.model

    print("=" * 72)
    print("CAREER OS - LLM JOB EVALUATION")
    print("=" * 72)
    print()
    print("Gate policy: only explicit candidate constraints applied before LLM.")
    print("  - Employment type gate: rejects internships, part-time, temporary")
    print("  - Recency gate:         rejects posts older than 30 days")
    print("  - NO role/domain/company/seniority assumptions block the LLM.")
    print()

    # --- Parse CV ---
    cv_path = args.cv
    if not Path(cv_path).exists():
        sys.exit(f"CV file not found: {cv_path}")
    print(f"[1/4] Parsing CV: {cv_path}")
    cv_text = parse_cv(cv_path)
    print(f"      CV text: {len(cv_text)} chars")

    # --- Load jobs ---
    jobs_path = args.jobs
    if not Path(jobs_path).exists():
        sys.exit(f"Jobs file not found: {jobs_path}")
    print(f"\n[2/4] Loading jobs: {jobs_path}")
    all_jobs = load_jobs(jobs_path)
    total = len(all_jobs)
    print(f"      Total jobs loaded: {total}")

    jobs_to_evaluate = all_jobs if args.all else all_jobs[: args.sample]
    print(f"      Jobs to process:   {len(jobs_to_evaluate)}")

    # --- LLM config ---
    llm_config = _llm_config()
    print(f"\n[3/4] LLM: {llm_config['provider']} / {llm_config['model']}")

    # --- Resume from previous run ---
    existing = load_existing_results(args.output)
    print(f"      Previously completed: {len(existing)}")

    # --- Evaluate ---
    print(f"\n[4/4] Running evaluations...\n")

    results        = []
    evaluated      = 0
    gate_rejected  = 0
    resumed        = 0
    errors         = 0

    for idx, job in enumerate(jobs_to_evaluate):
        job_id  = job["job_id"]
        title   = job.get("title", "UNKNOWN")
        company = job.get("company", "UNKNOWN")

        print(f"  [{idx+1}/{len(jobs_to_evaluate)}] {title[:58]}  |  {company[:28]}")

        # --- Resume: already done ---
        if job_id in existing:
            results.append(existing[job_id])
            resumed += 1
            print(f"    LLM CALLED: SKIPPED (already evaluated in previous run)")
            continue

        # --- Explicit constraint gates ---
        gate_passed, passed_gates, failed_gates = True, [], []
        if not args.skip_gates:
            gate_passed, passed_gates, failed_gates = run_explicit_constraint_gates(job)

        if not gate_passed:
            print(f"    LLM CALLED: NO  (explicit constraint gate failed)")
            for reason in failed_gates:
                print(f"      REJECTED: {reason}")
            gate_rejected += 1
            results.append({
                "job_id":              job_id,
                "discovery_id":        job.get("discovery_id", job_id),
                "title":               title,
                "company":             company,
                "location":            job.get("location", ""),
                "application_url":     job.get("job_url", ""),
                "is_remote":           job.get("is_remote", False),
                "salary_min":          job.get("salary_min"),
                "salary_max":          job.get("salary_max"),
                "salary_interval":     job.get("salary_interval", ""),
                "job_type":            job.get("job_type", ""),
                "site":                job.get("site", job.get("source", "")),
                "date_posted":         job.get("date_posted", ""),
                "provenance":          job.get("provenance", {}),
                "gate_failed":         True,
                "gate_failure_reasons": failed_gates,
                "gate_passed_checks":  passed_gates,
                "llm_evaluation":      None,
            })
            save_results(results, args.output, {
                "jobs_file": jobs_path, "cv_file": cv_path,
                "llm_model": llm_config["model"], "total_jobs_in_file": total,
            })
            continue

        # --- LLM evaluation ---
        print(f"    LLM CALLED: YES")
        prompt = build_prompt(cv_text, job)

        try:
            raw_response = call_llm(prompt, llm_config)
            ev_data = extract_json(raw_response)
            ev_data = validate_evaluation(ev_data)
            evaluated += 1

            rec   = ev_data["recommendation"]
            score = ev_data["overall_score"]
            prob  = ev_data["probability_of_obtaining"]
            diff  = ev_data["transition_difficulty"]
            print(f"    >> [{rec}]  score={score}  P(get)={prob}%  difficulty={diff}")

        except Exception as e:
            errors += 1
            print(f"    LLM ERROR: {e}")
            ev_data = {
                "role_fit": 0, "current_experience_fit": 0,
                "transferable_capability_fit": 0, "seniority_fit": 0,
                "opportunity_alignment": 0, "transition_difficulty": "unknown",
                "missing_critical_skills": [], "key_strengths": [],
                "career_upside": "unknown", "compensation_upside": "unknown",
                "probability_of_obtaining": 0, "confidence": "low",
                "recommendation": "Skip",
                "reasoning": "Evaluation error: " + str(e),
                "evidence": "UNKNOWN", "missing_evidence": "UNKNOWN",
                "overall_score": 0, "_error": str(e),
            }

        results.append({
            "job_id":              job_id,
            "discovery_id":        job.get("discovery_id", job_id),
            "title":               title,
            "company":             company,
            "location":            job.get("location", ""),
            "application_url":     job.get("job_url", ""),
            "is_remote":           job.get("is_remote", False),
            "salary_min":          job.get("salary_min"),
            "salary_max":          job.get("salary_max"),
            "salary_interval":     job.get("salary_interval", ""),
            "job_type":            job.get("job_type", ""),
            "site":                job.get("site", job.get("source", "")),
            "date_posted":         job.get("date_posted", ""),
            "provenance":          job.get("provenance", {}),
            "gate_failed":         False,
            "gate_failure_reasons": [],
            "gate_passed_checks":  passed_gates,
            "llm_evaluation":      ev_data,
        })

        # Save after every job — interrupted runs lose nothing
        save_results(results, args.output, {
            "jobs_file": jobs_path, "cv_file": cv_path,
            "llm_model": llm_config["model"], "total_jobs_in_file": total,
        })

        # Rate-limit pause between API calls (free tier needs breathing room)
        if idx < len(jobs_to_evaluate) - 1:
            time.sleep(INTER_CALL_PAUSE)

    # --- Final summary ---
    print(f"\n{'='*72}")
    print(
        f"COMPLETE:  llm_evaluated={evaluated}  gate_rejected={gate_rejected}  "
        f"resumed={resumed}  errors={errors}"
    )
    print(f"Output:    {args.output}")

    llm_evaluated_results = [r for r in results if not r.get("gate_failed")]
    if llm_evaluated_results:
        print_summary(results)


if __name__ == "__main__":
    main()
