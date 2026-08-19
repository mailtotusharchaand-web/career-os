"""
Career OS Scoring Package
"""

from career_os.scoring.config import CandidatePolicy, DEFAULT_POLICY
from career_os.scoring.gates import (
    is_product_role,
    check_employment_type,
    check_recency,
    check_seniority_compatibility,
    check_location_compatibility,
    run_all_gates,
    classify_seniority
)
from career_os.scoring.soft_score import (
    calculate_soft_score,
    calculate_category,
    domain_fit_score,
    seniority_match_score,
    role_specificity_score,
    skill_overlap_score,
    location_fit_score,
    classify_domain
)
from career_os.scoring.evaluator import (
    evaluate_job,
    evaluate_jobs,
    summarize_evaluation,
    filter_by_category,
    get_top_n
)

__all__ = [
    "CandidatePolicy",
    "DEFAULT_POLICY",
    "is_product_role",
    "check_employment_type",
    "check_recency",
    "check_seniority_compatibility",
    "check_location_compatibility",
    "run_all_gates",
    "classify_seniority",
    "calculate_soft_score",
    "calculate_category",
    "domain_fit_score",
    "seniority_match_score",
    "role_specificity_score",
    "skill_overlap_score",
    "location_fit_score",
    "classify_domain",
    "evaluate_job",
    "evaluate_jobs",
    "summarize_evaluation",
    "filter_by_category",
    "get_top_n"
]