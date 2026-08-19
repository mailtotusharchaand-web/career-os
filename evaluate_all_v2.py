import json

# Load jobs
jobs = json.load(open('tier1_jobs.json'))

evaluated = []

for i, job in enumerate(jobs):
    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    site = job.get("site", "")
    url = job.get("job_url", "")
    is_remote = job.get("is_remote", False)
    description = job.get("description", "")[:2000] if job.get("description") else ""
    salary_min = job.get("salary_min")
    salary_max = job.get("salary_max")
    salary_interval = job.get("salary_interval", "")
    job_type = job.get("job_type", "")
    
    title_lower = title.lower()
    desc_lower = description.lower()
    loc_lower = location.lower()
    
    # --- Determine if Product role ---
    is_product_role = any(kw in title_lower for kw in [
        "product manager", "product analyst", "product owner", "product designer",
        "associate product", "senior product", "principal product", "staff product",
        "technical product manager", "digital product", "product lead",
        "product management", "product lead"
    ])
    
    # --- Determine seniority ---
    seniority = "Mid-level"
    if any(kw in title_lower for kw in ["vp", "vice president", "director", "principal", "staff", "head of", "dvp", "avp", "srvp"]):
        seniority = "VP/Director/Principal/Staff"
    elif any(kw in title_lower for kw in ["senior", "sr.", "sr ", "lead", "manager"]):
        seniority = "Senior/Lead/Manager"
    elif any(kw in title_lower for kw in ["associate", "assoc"]):
        seniority = "Associate"
    elif any(kw in title_lower for kw in ["intern", "junior", "entry", "trainee"]):
        seniority = "Junior/Intern"
    
    # --- Determine domain ---
    domain = "Unknown"
    if any(kw in title_lower for kw in ["payments", "payment", "card", "billing", "transaction", "wallet", "tokenization", "rails"]):
        domain = "Payments"
    elif any(kw in title_lower for kw in ["kyc", "aml", "compliance", "risk", "fraud", "sanctions", "financial crime", "anti money laundering"]):
        domain = "KYC/AML/Compliance/Risk"
    elif any(kw in title_lower for kw in ["case management", "client implementation", "onboarding", "case", "dispute", "chargeback"]):
        domain = "Case Management"
    elif any(kw in title_lower for kw in ["identity", "auth", "authentication", "verification", "access", "tokenization", "profile"]):
        domain = "Identity/Access/Verification"
    elif any(kw in title_lower for kw in ["platform", "ecosystem", "risk platform", "trust and safety", "trust & safety"]):
        domain = "Platform/Trust & Safety"
    elif any(kw in title_lower for kw in ["deposit", "treasury", "wealth", "banking", "loan", "mortgage", "credit", "underwriting"]):
        domain = "Banking/Wealth/Credit"
    elif any(kw in title_lower for kw in ["marketing", "growth", "acquisition", "pricing", "strategy"]):
        domain = "Marketing/Growth"
    elif any(kw in title_lower for kw in ["data", "analytics", "analyst", "data scientist", "insights", "data engineer"]):
        domain = "Data/Analytics"
    elif any(kw in title_lower for kw in ["engineering", "technical", "technical product", "technical pm", "technical product manager", "software engineer", "devops", "sre"]):
        domain = "Technical/Engineering"
    elif any(kw in title_lower for kw in ["operations", "ops", "support lead", "support", "customer success", "client success"]):
        domain = "Operations/Support"
    elif any(kw in title_lower for kw in ["sales", "business development", "relationship manager", "account manager"]):
        domain = "Sales/Relationship"
    elif any(kw in title_lower for kw in ["legal", "counsel", "compliance", "regulatory"]):
        domain = "Legal/Compliance"
    elif any(kw in title_lower for kw in ["finance", "financial", "pricing", "pricing manager"]):
        domain = "Finance"
    elif any(kw in title_lower for kw in ["program manager", "project manager", "project"]):
        domain = "Program/Project Management"
    elif any(kw in title_lower for kw in ["retail", "merchandise", "stylist", "front desk", "cashier", "guest experience"]):
        domain = "Retail/Store Operations"
    elif any(kw in title_lower for kw in ["consultant", "consulting", "advisory"]):
        domain = "Consulting"
    elif any(kw in title_lower for kw in ["healthcare", "pharma", "clinical", "medical"]):
        domain = "Healthcare/Pharma"
    elif any(kw in title_lower for kw in ["automotive", "auto", "vehicle"]):
        domain = "Automotive"
    elif any(kw in title_lower for kw in ["media", "entertainment", "content"]):
        domain = "Media/Entertainment"
    elif any(kw in title_lower for kw in ["crypto", "blockchain", "web3", "okx"]):
        domain = "Crypto/Blockchain"
    elif any(kw in title_lower for kw in ["security", "securitas", "identity", "id"]):
        domain = "Security/Identity"
    
    # --- Location eligibility ---
    eligibility = "unknown"
    if is_remote:
        if any(kw in loc_lower for kw in ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "chandigarh", "delhi", "noida", "chennai", "kolkata", "ahmedabad"]):
            eligibility = "india_remote"
        elif "us" in loc_lower or "united states" in loc_lower or "remote, us" in loc_lower or "remote us" in loc_lower or "usa" in loc_lower:
            eligibility = "us_remote"
        else:
            eligibility = "international_remote"
    else:
        if any(kw in loc_lower for kw in ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "chandigarh", "delhi", "noida", "chennai", "kolkata", "ahmedabad"]):
            eligibility = "india_hybrid"
        elif "us" in loc_lower or "united states" in loc_lower or "usa" in loc_lower:
            eligibility = "us_onsite"
        else:
            eligibility = "other_onsite"
    
    # --- Scoring components (0-100 each) ---
    
    # role_fit: 0-100
    if is_product_role:
        role_fit = 85  # Strong product role match
    elif "analyst" in title_lower and domain in ["Payments", "KYC/AML/Compliance/Risk", "Data/Analytics"]:
        role_fit = 60  # Analyst in relevant domain
    else:
        role_fit = 10  # Not a product role
    
    # seniority_fit: 0-100
    if seniority == "Associate":
        seniority_fit = 95  # Perfect match
    elif seniority == "Mid-level":
        seniority_fit = 85  # Good match
    elif seniority == "Senior/Lead/Manager":
        if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]:
            seniority_fit = 75  # Stretch but acceptable for primary domains
        else:
            seniority_fit = 50  # Senior but wrong domain
    elif seniority == "VP/Director/Principal/Staff":
        if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]:
            seniority_fit = 40  # Overqualified but domain match
        else:
            seniority_fit = 15  # Overqualified + wrong domain
    elif seniority == "Junior/Intern":
        seniority_fit = 25  # Underqualified
    
    # domain_fit: 0-100
    primary_domains = ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]
    secondary_domains = ["Platform/Trust & Safety", "Banking/Wealth/Credit"]
    
    if domain in primary_domains:
        domain_fit = 95
    elif domain in secondary_domains:
        domain_fit = 70
    elif domain in ["Data/Analytics", "Platform/Trust & Safety", "Banking/Wealth/Credit"]:
        domain_fit = 55
    elif domain in ["Technical/Engineering", "Program/Project Management", "Operations/Support"]:
        domain_fit = 30
    elif domain in ["Marketing/Growth", "Sales/Relationship", "Legal/Compliance", "Finance", "Consulting"]:
        domain_fit = 20
    elif domain in ["Retail/Store Operations", "Healthcare/Pharma", "Automotive", "Media/Entertainment", "Crypto/Blockchain", "Security/Identity"]:
        domain_fit = 10
    else:
        domain_fit = 5
    
    # experience_fit: 0-100 (based on 5 years experience)
    if seniority in ["Associate", "Mid-level"]:
        experience_fit = 90  # 5 years matches well
    elif seniority == "Senior/Lead/Manager":
        if domain in primary_domains:
            experience_fit = 70  # 5 years is stretch but domain compensates
        else:
            experience_fit = 45
    elif seniority == "VP/Director/Principal/Staff":
        experience_fit = 20  # Overqualified
    elif seniority == "Junior/Intern":
        experience_fit = 35  # Underqualified
    
    # skill_fit: 0-100 (based on description keywords)
    skill_keywords = ["sql", "python", "api", "pega", "ace", "clic", "jira", "confluence", "rally", "sharepoint", "power bi", "tableau", "dashboard", "rca", "root cause", "uat", "user acceptance", "backlog", "roadmap", "prd", "mvp", "stakeholder", "cross-functional", "release", "compliance", "kyc", "aml", "risk", "payments", "payments", "case management"]
    skill_match = 0
    for kw in skill_keywords:
        if kw in desc_lower:
            skill_match += 1
    # Normalize: 0-15 matches -> 0-100
    skill_fit = min(95, 30 + skill_match * 5)  # Base 30, +5 per keyword match
    if skill_fit > 95:
        skill_fit = 95
    if not is_product_role and domain not in primary_domains:
        skill_fit = min(skill_fit, 40)
    
    # location_fit: 0-100
    if eligibility in ["india_remote", "international_remote", "us_remote"]:
        location_fit = 95
    elif eligibility == "india_hybrid":
        location_fit = 80
    elif eligibility == "us_onsite":
        if domain in primary_domains:
            location_fit = 60  # Willing to relocate for primary domain
        else:
            location_fit = 35
    elif eligibility == "india_hybrid":
        location_fit = 80
    else:
        location_fit = 25
    
    # --- Weighted overall score ---
    weights = {
        "role_fit": 0.15,
        "seniority_fit": 0.20,
        "domain_fit": 0.25,
        "experience_fit": 0.15,
        "skill_fit": 0.15,
        "location_fit": 0.10
    }
    
    overall = int(
        role_fit * weights["role_fit"] +
        seniority_fit * weights["seniority_fit"] +
        domain_fit * weights["domain_fit"] +
        experience_fit * weights["experience_fit"] +
        skill_fit * weights["skill_fit"] +
        location_fit * weights["location_fit"]
    )
    overall = min(100, max(0, overall))
    
    # --- Category ---
    if overall >= 75:
        category = "A"
    elif overall >= 55:
        category = "B"
    elif overall >= 35:
        category = "C"
    else:
        category = "D"
    
    # --- Why it matches ---
    why_parts = []
    if is_product_role:
        why_parts.append(f"Product role ({title}) matches target functions")
    else:
        why_parts.append(f"Not a core Product role ({title})")
    
    if domain in primary_domains:
        why_parts.append(f"Domain ({domain}) aligns with primary domains")
    elif domain in secondary_domains:
        why_parts.append(f"Domain ({domain}) is secondary priority")
    else:
        why_parts.append(f"Domain ({domain}) is not a target domain")
    
    if seniority in ["Associate", "Mid-level"]:
        why_parts.append(f"Seniority ({seniority}) matches 5 years experience")
    elif seniority == "Senior/Lead/Manager":
        why_parts.append(f"Seniority ({seniority}) is stretch but possible with domain")
    else:
        why_parts.append(f"Seniority ({seniority}) mismatched")
    
    if eligibility in ["india_remote", "international_remote", "us_remote"]:
        why_parts.append("Remote work eligible")
    elif eligibility == "india_hybrid":
        why_parts.append("Hybrid in India metros acceptable")
    elif eligibility == "us_onsite" and domain in primary_domains:
        why_parts.append("US on-site acceptable for primary domain (willing to relocate)")
    else:
        why_parts.append(f"Location ({eligibility}) not preferred")
    
    why_it_matches = "; ".join(why_parts)
    
    # --- Major gaps ---
    gap_parts = []
    if not is_product_role:
        gap_parts.append("Not a Product role")
    if domain not in primary_domains and domain not in secondary_domains:
        gap_parts.append(f"Domain ({domain}) not in target domains")
    if seniority in ["VP/Director/Principal/Staff", "Junior/Intern"]:
        gap_parts.append(f"Seniority ({seniority}) mismatch")
    if eligibility not in ["india_remote", "international_remote", "us_remote", "india_hybrid"] and not (eligibility == "us_onsite" and domain in primary_domains):
        gap_parts.append(f"Location ({eligibility}) not preferred")
    if skill_fit < 50:
        gap_parts.append("Limited skill overlap in description")
    if not gap_parts:
        gap_parts.append("No major gaps identified")
    major_gaps = "; ".join(gap_parts)
    
    # --- Recommendation ---
    if category == "A":
        rec = "Strong apply - strong domain + seniority + location match"
    elif category == "B":
        rec = "Worth considering - good domain match, minor gaps in seniority/location"
    elif category == "C":
        rec = "Weak match - domain or seniority partially aligned, significant gaps"
    else:
        rec = "Reject - not a Product role, wrong seniority, wrong domain, or location mismatch"
    
    eval_job = {
        "title": title,
        "company": company,
        "location": location,
        "source": site,
        "application_url": url,
        "overall_score": overall,
        "role_fit": role_fit,
        "seniority_fit": seniority_fit,
        "domain_fit": domain_fit,
        "experience_fit": experience_fit,
        "skill_fit": skill_fit,
        "location_fit": location_fit,
        "category": category,
        "eligibility": eligibility,
        "why_it_matches": why_it_matches,
        "major_gaps": major_gaps,
        "recommendation": rec
    }
    
    evaluated.append(eval_job)

# Sort
evaluated.sort(key=lambda x: -x["overall_score"])

# Split categories
strong_apply = [j for j in evaluated if j["category"] == "A"]
worth_considering = [j for j in evaluated if j["category"] == "B"]
top_20 = evaluated[:20]
top_10 = evaluated[:10]

# Summary stats
product_count = len([j for j in evaluated if any(kw in j["title"].lower() for kw in [
    "product manager", "product analyst", "product owner", "product designer",
    "associate product", "senior product", "principal product", "staff product",
    "technical product manager", "digital product", "product lead"
])])

output = {
    "candidate_profile": {
        "current_role": "Associate — Digital Product Management (CLIC Platform, PEGA/ACE)",
        "company": "American Express (India) Pvt. Ltd., Gurugram",
        "total_relevant_experience_years": 5,
        "target_functions": ["Product Analyst", "Associate Product Manager", "Product Manager", "Digital Product Manager", "Product Owner"],
        "target_seniority": "Associate → Mid-level (0–5 years PM experience); open to Senior PM if domain match is strong",
        "primary_domains": ["Fintech", "Payments", "Risk", "Compliance", "KYC/AML", "Enterprise Case Management"],
        "secondary_domains": ["B2B SaaS", "Financial Services", "RegTech"],
        "strongest_skills": ["Product Discovery", "MVP Definition", "PRDs", "Roadmapping", "User Stories", "Acceptance Criteria", "Backlog Prioritization", "Sprint Planning", "Release Readiness", "Stakeholder Management"],
        "technical_product_skills": ["SQL", "Python (dashboards/automation)", "API debugging", "RCA", "Operational metrics", "Power BI", "Tableau", "PEGA/ACE/CLIC platform expertise"],
        "tools_platforms": ["Jira", "Rally", "Confluence", "PEGA (CLIC/ACE)", "SharePoint"],
        "certifications": ["CSPO (Scrum Alliance)", "SAFe POPM (Scaled Agile, Inc.)", "Python (Basic) - HackerRank", "SQL (Basic) - HackerRank"],
        "geographic_preference": {"primary": "Remote (US/Global)", "secondary": "Gurugram/Delhi NCR, Bangalore, Hyderabad, Pune, Mumbai", "willing_to_relocate": "For strong domain match"},
        "remote_preference": "Strong",
        "important_experience_signals": ["250K–300K monthly case flows (RBST/PBST)", "40+ pre-launch defects caught in KYC automation (3-system)", "15% compliance accuracy improvement", "AI-assisted case processing solutioning", "Cross-border regulatory rollout (Belgium KYC)", "Release leadership under PO/SM absence"],
        "obvious_exclusions_mismatches": ["Pure software engineering", "Aerospace/defense", "Hardware/firmware/RTOS", "Pure data engineering / ML engineering", "Sales / commercial roles", "Early-career / internship roles", "Roles requiring security clearance (US Federal)"]
    },
    "evaluation_summary": {
        "total_evaluated": 196,
        "category_counts": {
            "A": len([j for j in evaluated if j["category"] == "A"]),
            "B": len([j for j in evaluated if j["category"] == "B"]),
            "C": len([j for j in evaluated if j["category"] == "C"]),
            "D": len([j for j in evaluated if j["category"] == "D"])
        },
        "average_score": sum(j["overall_score"] for j in evaluated) // len(evaluated),
        "median_score": sorted([j["overall_score"] for j in evaluated])[len(evaluated)//2],
        "product_roles": product_count,
        "non_product_roles": 196 - product_count,
        "india_roles": len([j for j in evaluated if any(kw in j["location"].lower() for kw in ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "chandigarh", "delhi", "noida"])]),
        "international_us_roles": len([j for j in evaluated if "us" in j["location"].lower() or "united states" in j["location"].lower() or "usa" in j["location"].lower()]),
        "unknown_eligibility": len([j for j in evaluated if j["eligibility"] == "unknown"]),
        "top_5_rejection_reasons": [
            "Not a Product role (retail, sales, marketing, ops, consulting, engineering, etc.)",
            "Wrong seniority (VP/Director/Principal/Staff/Manager level)",
            "Wrong domain (retail, healthcare, pharma, automotive, entertainment, defense, crypto, etc.)",
            "Wrong function (Engineering/Technical PM, Data Science, Analytics, Ops, Marketing, Sales, Legal, Finance)",
            "On-site / hybrid only in non-preferred locations (no remote option)"
        ]
    },
    "evaluated_jobs": evaluated,
    "strong_apply": [j for j in evaluated if j["category"] == "A"],
    "worth_considering": [j for j in evaluated if j["category"] == "B"],
    "top_20": evaluated[:20],
    "top_10": evaluated[:10]
}

with open('14-JOB-EVALUATION.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)

print("Evaluation complete!")
print(f"Total evaluated: {len(evaluated)}")
print(f"A: {len([j for j in evaluated if j['category'] == 'A'])}")
print(f"B: {len([j for j in evaluated if j['category'] == 'B'])}")
print(f"C: {len([j for j in evaluated if j['category'] == 'C'])}")
print(f"D: {len([j for j in evaluated if j['category'] == 'D'])}")
print(f"Product roles: {product_count}")
print(f"Average score: {output['evaluation_summary']['average_score']}")
print(f"Median score: {output['evaluation_summary']['median_score']}")

# Print A and B jobs
for j in evaluated:
    if j['category'] in ['A', 'B']:
        print(f"{j['category']} ({j['overall_score']}): {j['title'][:50]} | {j['company'][:25]} | {j['location'][:25]} | {j['eligibility']} | domain_fit={j['domain_fit']} | loc_fit={j['location_fit']}")