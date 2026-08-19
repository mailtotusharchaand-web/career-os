"""
Career OS — Hard Gates
Binary pass/fail checks that must ALL pass before soft scoring.
"""

from typing import Tuple, List
from career_os.scoring.config import (
    CandidatePolicy,
    infer_domain,
    PRODUCT_EXCLUDE_KEYWORDS,
    EMPLOYMENT_EXCLUDE_KEYWORDS,
    SENIORITY_VP_KEYWORDS,
    SENIORITY_SENIOR_KEYWORDS,
    SENIORITY_ASSOCIATE_KEYWORDS,
    PRIMARY_DOMAINS,
    normalize_domain
)


def is_product_role(title: str) -> Tuple[bool, str]:
    """
    Gate 1: Product Function
    Returns (passes, reason)
    """
    title_lower = title.lower()
    
    # Check exclusions first
    for ex in PRODUCT_EXCLUDE_KEYWORDS:
        if ex in title_lower:
            return False, f"Excluded keyword: '{ex}'"
    
    # Check for product keywords
    product_keywords = [
        "product manager", "product analyst", "product owner",
        "associate product", "senior product", "principal product",
        "staff product", "lead product", "group product",
        "digital product", "technical product manager",
        "product management", "product lead", "product lead",
        "associate product manager", "product analyst"
    ]
    
    for pk in product_keywords:
        if pk in title_lower:
            return True, f"Product keyword: '{pk}'"
    
    return False, "No product function keyword found"


def check_employment_type(job_type: str, title: str, policy) -> Tuple[bool, str]:
    """
    Gate 2: Employment Type
    """
    title_lower = title.lower()
    job_type_lower = (job_type or "").lower()
    
    for term in EMPLOYMENT_EXCLUDE_KEYWORDS:
        if term in title_lower:
            return False, f"Excluded in title: '{term}'"
        if term in job_type_lower:
            return False, f"Excluded in job_type: '{term}'"
    
    if not policy.contract_acceptable and "contract" in job_type_lower:
        return False, "Contract not acceptable per policy"
    if not policy.part_time_acceptable and "part" in job_type_lower:
        return False, "Part-time not acceptable per policy"
    if not policy.temporary_acceptable and "temporary" in job_type_lower:
        return False, "Temporary not acceptable per policy"
    
    return True, "Employment type acceptable"


def check_recency(date_posted: str, policy) -> Tuple[bool, str]:
    """
    Gate 3: Recency
    """
    if not date_posted:
        return True, "No date posted (not penalized)"
    
    try:
        from datetime import datetime
        # Try common formats
        for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"]:
            try:
                posted = datetime.strptime(date_posted[:19], fmt[:19])
                break
            except ValueError:
                continue
        else:
            return True, f"Unknown date format: {date_posted}"
        
        days_old = (datetime.now() - posted).days
        if days_old > 30:
            return False, f"Posted {days_old} days ago (>{30} days)"
        return True, f"Posted {days_old} days ago"
    except Exception as e:
        return True, f"Date parse error: {e}"


def classify_seniority(title: str) -> str:
    """Classify seniority from title."""
    title_lower = title.lower()
    
    if any(kw in title_lower for kw in SENIORITY_VP_KEYWORDS):
        return "vp"
    if any(kw in title_lower for kw in SENIORITY_SENIOR_KEYWORDS):
        return "senior"
    if any(kw in title_lower for kw in SENIORITY_ASSOCIATE_KEYWORDS):
        return "associate"
    return "mid"


def check_seniority_compatibility(title: str, domain: str, policy) -> Tuple[bool, str]:
    """
    Gate 4: Seniority Compatibility
    """
    seniority = classify_seniority(title)
    
    # Check min/max
    seniority_order = ["associate", "mid", "senior", "vp"]
    min_idx = seniority_order.index(policy.min_seniority)
    max_idx = seniority_order.index(policy.max_seniority)
    curr_idx = seniority_order.index(seniority)
    
    if curr_idx < min_idx:
        return False, f"Seniority '{seniority}' below minimum '{policy.min_seniority}'"
    if curr_idx > max_idx:
        # Check if stretch allowed for primary domain
        if seniority == "vp" and policy.seniority_stretch_acceptable:
            # Would need domain check - handled in location compatibility
            pass
        else:
            return False, f"Seniority '{seniority}' above maximum '{policy.max_seniority}'"
    
    return True, f"Seniority '{seniority}' within range"


def check_location_compatibility(location: str, is_remote: bool, domain: str, policy) -> Tuple[bool, str]:
    """
    Gate 5: Location Compatibility
    """
    loc_lower = (location or "").lower()
    
    # Check if India location
    india_keywords = ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "noida", "chennai", "kolkata", "ahmedabad"]
    is_india = any(kw in loc_lower for kw in india_keywords)
    
    # Check if US location
    us_keywords = ["us", "united states", "usa", "remote, us", "remote us"]
    is_us = any(kw in loc_lower for kw in us_keywords)
    
    # India locations always eligible
    if is_india:
        return True, "India location eligible"
    
    # International remote (not US, not India)
    if is_remote and not is_us and not is_india:
        return True, "International remote eligible"
    
    # US remote
    if is_us and is_remote:
        return True, "US remote eligible"
    
    # US on-site
    if is_us and not is_remote:
        # Check if willing to relocate for primary domain
        if policy.willing_to_relocate_us:
            # Check if domain is primary
            from career_os.scoring.config import PRIMARY_DOMAINS
            if any(normalize_domain(domain) == normalize_domain(d) for d in PRIMARY_DOMAINS):
                return True, f"US on-site eligible (willing to relocate for primary domain: {domain})"
        return False, "US on-site not eligible (not willing to relocate)"
    
    # Other on-site
    if policy.willing_to_relocate_other:
        from career_os.scoring.config import PRIMARY_DOMAINS
        if any(normalize_domain(domain) == normalize_domain(d) for d in PRIMARY_DOMAINS):
            return True, f"On-site eligible (willing to relocate for primary domain: {domain})"
    return False, f"On-site in non-preferred location: {location}"


def check_domain_compatibility(domain: str, policy) -> Tuple[bool, str]:
    """
    Check domain against policy (used in scoring, not a hard gate)
    """
    domain_lower = domain.lower()
    
    if domain_lower in [d.lower() for d in policy.excluded_domains]:
        return False, f"Domain '{domain}' in excluded list"
    
    return True, f"Domain '{domain}' acceptable"


def run_all_gates(job: dict, policy) -> Tuple[bool, List[str], List[str]]:
    """
    Run all hard gates.
    Returns (all_passed, passed_gates, failed_gates)
    """
    passed = []
    failed = []
    
    # Infer domain from title/description
    title = job.get("title", "")
    description = job.get("description", "")[:2000] if job.get("description") else ""
    inferred_domain = infer_domain(title, description)
    
    # Gate 1: Product Function
    passes, reason = is_product_role(title)
    if passes:
        passed.append(f"Product Function: {reason}")
    else:
        failed.append(f"Product Function: {reason}")
    
    # Gate 2: Employment Type
    passes, reason = check_employment_type(job.get("job_type", ""), title, policy)
    if passes:
        passed.append(f"Employment Type: {reason}")
    else:
        failed.append(f"Employment Type: {reason}")
    
    # Gate 3: Recency
    passes, reason = check_recency(job.get("date_posted", ""), policy)
    if passes:
        passed.append(f"Recency: {reason}")
    else:
        failed.append(f"Recency: {reason}")
    
    # Gate 4: Seniority Compatibility
    passes, reason = check_seniority_compatibility(title, inferred_domain, policy)
    if passes:
        passed.append(f"Seniority: {reason}")
    else:
        failed.append(f"Seniority: {reason}")
    
    # Gate 5: Location Compatibility
    passes, reason = check_location_compatibility(
        job.get("location", ""), job.get("is_remote", False), inferred_domain, policy
    )
    if passes:
        passed.append(f"Location: {reason}")
    else:
        failed.append(f"Location: {reason}")
    
    all_passed = len(failed) == 0
    return all_passed, passed, failed