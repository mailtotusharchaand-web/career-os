"""
Career OS — Main Evaluator
Orchestrates hard gates + soft score.
"""

from typing import Dict, Any, List, Optional
from career_os.scoring.config import CandidatePolicy, DEFAULT_POLICY
from career_os.scoring.gates import run_all_gates
from career_os.scoring.soft_score import calculate_soft_score, calculate_category


def generate_recommendation(category: str, score: int, job: dict) -> str:
    """Generate human-readable recommendation."""
    title = job.get("title", "")
    company = job.get("company", "")
    
    if category == "A":
        return f"Strong apply — {title} at {company} scores {score}. Strong domain/role/location alignment."
    if category == "B":
        return f"Worth considering — {title} at {company} scores {score}. Good domain match, minor gaps."
    if category == "C":
        return f"Weak match — {title} at {company} scores {score}. Partial alignment, significant gaps."
    return f"Reject — {title} at {company} fails hard gates or scores {score}."


def evaluate_job(job: dict, policy: Optional[CandidatePolicy] = None) -> Dict[str, Any]:
    """
    Complete job evaluation.
    Returns dict with gates, soft score, category, recommendation.
    """
    if policy is None:
        policy = DEFAULT_POLICY
    
    # Run hard gates
    all_passed, passed_gates, failed_gates = run_all_gates(job, policy)
    
    gate_failures = [f.split(": ")[1] if ": " in f else f for f in failed_gates]
    
    if not all_passed:
        return {
            "job_id": job.get("job_id", ""),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "source": job.get("site", ""),
            "application_url": job.get("job_url", ""),
            "overall_score": 0,
            "category": "D",
            "hard_gates": {
                "passed": passed_gates,
                "failed": failed_gates
            },
            "gate_failures": gate_failures,
            "soft_score": None,
            "breakdown": None,
            "domain_classification": None,
            "recommendation": f"Reject — Hard gate failures: {', '.join(gate_failures)}",
            "eligibility": job.get("location", "")
        }
    
    # All gates passed — compute soft score
    soft = calculate_soft_score(job, None)
    score = soft["score"]
    category = calculate_category(score)
    
    return {
        "job_id": job.get("job_id", ""),
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "source": job.get("site", ""),
        "application_url": job.get("job_url", ""),
        "overall_score": score,
        "category": category,
        "hard_gates": {
            "passed": passed_gates,
            "failed": []
        },
        "gate_failures": [],
        "soft_score": score,
        "breakdown": soft["breakdown"],
        "domain_classification": soft["domain_classification"],
        "recommendation": generate_recommendation(category, score, job),
        "eligibility": "eligible"  # All gates passed
    }


def evaluate_jobs(jobs: List[dict], policy: Optional[CandidatePolicy] = None) -> List[dict]:
    """Evaluate a list of jobs."""
    return [evaluate_job(job, policy) for job in jobs]


def summarize_evaluation(evaluations: List[dict]) -> Dict[str, Any]:
    """Generate summary statistics."""
    categories = {"A": 0, "B": 0, "C": 0, "D": 0}
    gate_failure_counts = {}
    
    for e in evaluations:
        categories[e["category"]] = categories.get(e["category"], 0) + 1
        for failure in e.get("gate_failures", []):
            gate_failure_counts[failure] = gate_failure_counts.get(failure, 0) + 1
    
    total = len(evaluations)
    scores = [e["overall_score"] for e in evaluations if e["overall_score"] > 0]
    
    return {
        "total_evaluated": total,
        "category_counts": categories,
        "average_score": sum(scores) // len(scores) if scores else 0,
        "median_score": sorted(scores)[len(scores)//2] if scores else 0,
        "top_gate_failures": sorted(gate_failure_counts.items(), key=lambda x: -x[1])[:10],
        "product_roles": sum(1 for e in evaluations if "product" in e["title"].lower() and ("manager" in e["title"].lower() or "analyst" in e["title"].lower() or "owner" in e["title"].lower())),
        "non_product_roles": sum(1 for e in evaluations if not ("product" in e["title"].lower() and ("manager" in e["title"].lower() or "analyst" in e["title"].lower() or "owner" in e["title"].lower()))),
        "eligible_jobs": sum(1 for e in evaluations if e["category"] != "D" or e["gate_failures"] == [])
    }


def filter_by_category(evaluations: List[dict], category: str) -> List[dict]:
    """Filter evaluations by category."""
    return [e for e in evaluations if e["category"] == category]


def get_top_n(evaluations: List[dict], n: int = 10) -> List[dict]:
    """Get top N jobs by score."""
    sorted_evals = sorted(evaluations, key=lambda x: -x["overall_score"])
    return sorted_evals[:n]