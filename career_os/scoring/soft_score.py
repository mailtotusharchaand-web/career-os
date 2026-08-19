"""
Career OS — Soft Score Calculation
Only computed if ALL hard gates pass.
"""

from typing import Dict, Any
from career_os.scoring.config import (
    CandidatePolicy,
    PRIMARY_DOMAINS,
    SECONDARY_DOMAINS,
    ADJACENT_DOMAINS,
    classify_domain,
    normalize_domain,
    infer_domain
)
from career_os.scoring.gates import classify_seniority


def domain_fit_score(domain: str, policy) -> int:
    """Domain fit: primary=95, secondary=70, adjacent=50, other=20, excluded=0."""
    cat = classify_domain(domain, None)
    scores = {
        "primary": 95,
        "secondary": 70,
        "adjacent": 50,
        "other": 20,
        "excluded": 0
    }
    return scores.get(cat, 0)


def classify_seniority(title: str) -> str:
    """Classify seniority from title."""
    title_lower = title.lower()
    
    if any(kw in title_lower for kw in ["vp", "vice president", "director", "principal", "staff", "head of", "dvp", "avp", "srvp", "evp", "svp"]):
        return "vp"
    if any(kw in title_lower for kw in ["senior", "sr.", "sr ", "lead", "manager"]):
        return "senior"
    if any(kw in title_lower for kw in ["associate", "assoc", "junior", "jr.", "jr "]):
        return "associate"
    return "mid"


def seniority_match_score(title: str, domain: str, policy) -> int:
    """
    Seniority match: associate=95, mid=85, senior=70 (primary), vp=30.
    """
    seniority = classify_seniority(title)
    domain_cat = classify_domain(domain, None)
    
    scores = {
        "associate": 95,
        "mid": 85,
        "senior": 70 if classify_domain(domain, None) == "primary" else 50,
        "vp": 30
    }
    return scores.get(seniority, 60)


def role_specificity_score(title: str) -> int:
    """
    Role specificity: exact title match scores higher.
    """
    title_lower = title.lower()
    
    if "product analyst" in title_lower:
        return 95
    if "associate product manager" in title_lower:
        return 90
    if "product manager" in title_lower and "senior" not in title_lower:
        return 85
    if "product owner" in title_lower:
        return 80
    if "digital product manager" in title_lower:
        return 75
    if "technical product manager" in title_lower:
        return 70
    if "product" in title_lower and "manager" in title_lower:
        return 65
    return 40


SKILL_KEYWORDS = [
    "sql", "python", "api", "pega", "ace", "clic", "jira", "confluence", 
    "rally", "sharepoint", "power bi", "tableau", "dashboard", "rca", 
    "root cause", "uat", "user acceptance", "backlog", "roadmap", "prd", 
    "mvp", "stakeholder", "cross-functional", "release", "compliance", 
    "kyc", "aml", "risk", "payments", "case management", "dispute", 
    "chargeback", "rbst", "pbst", "smart assign", "ai", "llm", "call transcript",
    "workflow", "defect", "rca", "root cause analysis", "release readiness",
    "sprint planning", "backlog prioritization", "acceptance criteria", "user stories"
]


def skill_overlap_score(description: str) -> int:
    """
    Skill overlap based on keyword matching in description.
    Base 30, +5 per keyword match, capped at 95.
    """
    if not description:
        return 30
    
    desc_lower = description.lower()
    matches = sum(1 for kw in SKILL_KEYWORDS if kw in desc_lower)
    score = min(95, 30 + matches * 5)
    return score


def location_fit_score(location: str, is_remote: bool, policy) -> int:
    """
    Location fit: india_remote=95, us_remote=90, india_hybrid=80, 
    us_onsite_willing=60, us_onsite=30, other=20
    """
    loc = (location or "").lower()
    
    # India
    india_keywords = ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "noida", "chennai", "kolkata", "ahmedabad"]
    if any(kw in loc.lower() for kw in ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "noida", "chennai", "kolkata", "ahmedabad"]):
        return 95 if is_remote else 80
    
    # US
    us_keywords = ["us", "united states", "usa", "remote, us", "remote us"]
    is_us = any(kw in loc.lower() for kw in ["us", "united states", "usa", "remote, us", "remote us"])
    
    if is_us:
        if is_remote:
            return 90
        # on-site US - only if willing to relocate
        return 60
    
    # International remote
    if is_remote:
        return 85
    
    # Other on-site
    return 20


def calculate_soft_score(job: dict, policy) -> Dict[str, Any]:
    """
    Calculate soft score with breakdown.
    Only called if all hard gates pass.
    """
    title = job.get("title", "")
    description = job.get("description", "")[:3000] if job.get("description") else ""
    location = job.get("location", "")
    is_remote = job.get("is_remote", False)
    
    # Infer domain from title/description
    domain = infer_domain(title, description)
    
    # Domain fit (30%)
    domain_fit = domain_fit_score(domain, None)
    
    # Seniority match (25%)
    seniority_match = seniority_match_score(job.get("title", ""), domain, None)
    
    # Role specificity (20%)
    role_spec = role_specificity_score(job.get("title", ""))
    
    # Skill overlap (15%)
    skill_overlap = skill_overlap_score(job.get("description", "")[:3000] if job.get("description") else "")
    
    # Location fit (10%)
    location_fit = location_fit_score(location, job.get("is_remote", False), None)
    
    # Weighted sum
    score = int(
        domain_fit * 0.30 +
        seniority_match * 0.25 +
        role_spec * 0.20 +
        skill_overlap * 0.15 +
        location_fit * 0.10
    )
    score = min(100, max(0, score))
    
    breakdown = {
        "domain_fit": domain_fit,
        "seniority_match": seniority_match,
        "role_specificity": role_spec,
        "skill_overlap": skill_overlap,
        "location_fit": location_fit
    }
    
    return {
        "score": score,
        "breakdown": breakdown,
        "domain_classification": classify_domain(infer_domain(job.get("title", ""), job.get("description", "")[:2000] if job.get("description") else ""), None)
    }
    
    return {
        "score": score,
        "breakdown": breakdown,
        "domain_classification": classify_domain(domain, None)
    }


def calculate_category(score: int) -> str:
    """Map score to category."""
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "D"