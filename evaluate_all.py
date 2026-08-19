import json

# Load jobs
jobs = json.load(open('tier1_jobs.json'))

# Candidate profile summary for reference
candidate = {
    "role": "Associate — Digital Product Management",
    "experience": 5,
    "domains": ["Fintech", "Payments", "KYC/AML", "Compliance", "Risk", "Case Management"],
    "target_titles": ["Product Analyst", "Associate PM", "Product Manager", "Digital PM", "Product Owner"],
    "seniority": "Associate to Mid-level",
    "location_pref": "Remote (US/Global), India metros secondary",
    "remote": True
}

evaluated = []
strong_apply = []
worth_considering = []

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
    
    # Evaluate against candidate profile
    title_lower = title.lower()
    desc_lower = description.lower()
    
    # Determine if Product role
    is_product_role = any(kw in title_lower for kw in [
        "product manager", "product analyst", "product owner", "product designer",
        "associate product", "senior product", "principal product", "staff product",
        "technical product manager", "digital product", "product lead"
    ]) or ("product" in title_lower and "manager" in title_lower)
    
    # Determine seniority
    seniority = "Unknown"
    if any(kw in title_lower for kw in ["vp", "vice president", "director", "principal", "staff", "head of", "dvp", "avp"]):
        seniority = "VP/Director/Principal/Staff"
    elif any(kw in title_lower for kw in ["senior", "sr.", "sr ", "lead", "manager"]):
        seniority = "Senior/Lead/Manager"
    elif any(kw in title_lower for kw in ["associate", "assoc"]):
        seniority = "Associate"
    elif any(kw in title_lower for kw in ["intern", "junior", "entry", "trainee"]):
        seniority = "Junior/Intern"
    else:
        seniority = "Mid-level"
    
    # Domain classification
    domain = "Unknown"
    if any(kw in title_lower for kw in ["payments", "payment", "card", "billing", "transaction", "wallet"]):
        domain = "Payments"
    elif any(kw in title_lower for kw in ["kyc", "aml", "compliance", "risk", "fraud", "sanctions", "financial crime"]):
        domain = "KYC/AML/Compliance/Risk"
    elif any(kw in title_lower for kw in ["case management", "client implementation", "onboarding", "case", "dispute", "chargeback"]):
        domain = "Case Management"
    elif any(kw in title_lower for kw in ["identity", "auth", "authentication", "verification", "access", "tokenization"]):
        domain = "Identity/Access/Verification"
    elif any(kw in title_lower for kw in ["aml", "anti money laundering", "financial crime"]):
        domain = "KYC/AML/Compliance/Risk"
    elif any(kw in title_lower for kw in ["platform", "ecosystem", "risk platform", "trust and safety", "trust & safety"]):
        domain = "Platform/Trust & Safety"
    elif any(kw in title_lower for kw in ["deposit", "treasury", "wealth", "banking", "loan", "mortgage", "credit", "underwriting"]):
        domain = "Banking/Wealth/Credit"
    elif any(kw in title_lower for kw in ["marketing", "growth", "acquisition", "pricing", "strategy"]):
        domain = "Marketing/Growth"
    elif any(kw in title_lower for kw in ["data", "analytics", "analyst", "data scientist", "insights"]):
        domain = "Data/Analytics"
    elif any(kw in title_lower for kw in ["engineering", "technical", "technical product", "technical pm", "technical product manager"]):
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
    elif any(kw in title_lower for kw in ["retail", "merchandise", "stylist", "front desk", "cashier", "stylist", "guest experience"]):
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
    
    # Location eligibility
    loc_lower = location.lower()
    eligibility = "unknown"
    if is_remote:
        if "india" in loc_lower or "gurugram" in loc_lower or "bangalore" in loc_lower or "hyderabad" in loc_lower or "pune" in loc_lower or "mumbai" in loc_lower or "chandigarh" in loc_lower:
            eligibility = "india_remote"
        elif "us" in loc_lower or "united states" in loc_lower or "remote, us" in loc_lower or "remote us" in loc_lower:
            eligibility = "us_remote"
        else:
            eligibility = "international_remote"
    else:
        if "india" in loc_lower or "gurugram" in loc_lower or "bangalore" in loc_lower or "hyderabad" in loc_lower or "pune" in loc_lower or "mumbai" in loc_lower or "chandigarh" in loc_lower:
            eligibility = "india_hybrid"
        elif "us" in loc_lower or "united states" in loc_lower:
            eligibility = "us_onsite"
        else:
            eligibility = "other_onsite"
    
    # Scoring logic
    overall = 0
    role_fit = 0
    seniority_fit = 0
    domain_fit = 0
    experience_fit = 0
    skill_fit = 0
    location_fit = 0
    
    category = "D"
    why = ""
    gaps = ""
    rec = ""
    
    # Start with base
    if is_product_role:
        overall += 20
        role_fit = 60
    else:
        role_fit = 0
    
    # Seniority fit
    if seniority == "Associate":
        seniority_fit = 90
        overall += 15
    elif seniority == "Mid-level":
        seniority_fit = 70
        overall += 10
    elif seniority == "Senior/Lead/Manager":
        if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]:
            seniority_fit = 60
            overall += 5
        else:
            seniority_fit = 30
    elif seniority == "VP/Director/Principal/Staff":
        seniority_fit = 10
    elif seniority == "Junior/Intern":
        seniority_fit = 10
    
    # Domain fit
    if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]:
        domain_fit = 90
        overall += 25
    elif domain in ["Platform/Trust & Safety", "Banking/Wealth/Credit"]:
        domain_fit = 60
        overall += 15
    elif domain in ["Data/Analytics", "Platform/Trust & Safety"]:
        domain_fit = 40
        overall += 10
    elif domain in ["Technical/Engineering", "Program/Project Management", "Operations/Support", "Operations/Support"]:
        domain_fit = 20
    elif domain in ["Operations/Support", "Sales/Relationship", "Legal/Compliance", "Finance", "Marketing/Growth", "Consulting"]:
        domain_fit = 10
    elif domain in ["Retail/Store Operations", "Healthcare/Pharma", "Automotive", "Media/Entertainment", "Crypto/Blockchain", "Security/Identity"]:
        domain_fit = 5
    
    # Experience fit - 5 years exp matches associate to mid
    if seniority in ["Associate", "Mid-level"]:
        experience_fit = 90
        overall += 10
    elif seniority == "Senior/Lead/Manager":
        if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management"]:
            experience_fit = 60
        else:
            experience_fit = 30
    elif seniority == "VP/Director/Principal/Staff":
        experience_fit = 10
    elif seniority == "Junior/Intern":
        experience_fit = 20
    
    # Skill fit - candidate has SQL, Python, API debugging, RCA, operational metrics, PEGA/ACE/CLIC
    if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Case Management", "Identity/Access/Verification"]:
        if "sql" in job.get("description", "").lower() or "python" in job.get("description", "").lower() or "api" in job.get("description", "").lower() or "pega" in job.get("description", "").lower() or "ace" in job.get("description", "").lower() or "clic" in job.get("description", "").lower():
            skill_fit = 80
        else:
            skill_fit = 60
    elif domain in ["Data/Analytics"]:
        skill_fit = 50
    else:
        skill_fit = 20
    
    # Location fit
    if eligibility in ["india_remote", "international_remote", "us_remote"]:
        location_fit = 90
    elif eligibility == "india_hybrid":
        location_fit = 60
    else:
        location_fit = 20
    
    # Calculate overall
    overall = min(100, int(overall))
    
    # Determine category
    if overall >= 75:
        category = "A"
    elif overall >= 55:
        category = "B"
    elif overall >= 35:
        category = "C"
    else:
        category = "D"
    
    # Generate why_it_matches
    why_parts = []
    if is_product_role:
        why_parts.append(f"Product role ({title}) matches target functions")
    else:
        why_parts.append(f"Not a core Product role ({title})")
    
    if domain in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]:
        why_parts.append(f"Domain ({domain}) aligns with candidate's primary domains")
    elif domain in ["Platform/Trust & Safety", "Banking/Wealth/Credit"]:
        why_parts.append(f"Domain ({domain}) is secondary priority")
    else:
        why_parts.append(f"Domain ({domain}) is not a target domain")
    
    if seniority in ["Associate", "Mid-level"]:
        why_parts.append(f"Seniority ({seniority}) matches candidate's 5 years experience")
    elif seniority == "Senior/Lead/Manager":
        why_parts.append(f"Seniority ({seniority}) is stretch but possible with strong domain")
    else:
        why_parts.append(f"Seniority ({seniority}) mismatched")
    
    if eligibility in ["india_remote", "international_remote", "us_remote"]:
        why_parts.append("Remote work eligible")
    elif eligibility == "india_hybrid":
        why_parts.append("Hybrid in India metros acceptable")
    else:
        why_parts.append(f"Location ({eligibility}) not preferred")
    
    why_it_matches = "; ".join(why_parts)
    
    # Major gaps
    gap_parts = []
    if not is_product_role:
        gap_parts.append("Not a Product role")
    if domain not in ["Payments", "KYC/AML/Compliance/Risk", "Case Management", "Identity/Access/Verification"]:
        gap_parts.append(f"Domain ({domain}) not in primary domains")
    if seniority in ["VP/Director/Principal/Staff", "Junior/Intern"]:
        gap_parts.append(f"Seniority ({seniority}) mismatch")
    if eligibility not in ["india_remote", "international_remote", "us_remote", "india_hybrid"]:
        gap_parts.append(f"Location ({eligibility}) not preferred")
    if skill_fit < 50:
        gap_parts.append("Limited skill overlap evidence in description")
    if not gap_parts:
        gap_parts.append("No major gaps identified")
    major_gaps = "; ".join(gap_parts)
    
    # Recommendation
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
    
    if category == "A":
        strong_apply.append(eval_job)
    elif category == "B":
        worth_considering.append(eval_job)

# Sort strong_apply and worth_considering by score
strong_apply.sort(key=lambda x: -x["overall_score"])
worth_considering.sort(key=lambda x: -x["overall_score"])

# Top 20
all_sorted = sorted(evaluated, key=lambda x: -x["overall_score"])
top_20 = all_sorted[:20]
top_10 = all_sorted[:10]

# Save full evaluation
output = {
    "candidate_profile": candidate,
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
        "product_roles": len([j for j in evaluated if "Product" in j["title"] and ("Manager" in j["title"] or "Analyst" in j["title"] or "Owner" in j["title"] or "Designer" in j["title"] or "Lead" in j["title"])]) if False else 0,
        "non_product_roles": 0,
        "india_roles": 0,
        "international_us_roles": 196,
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
    "strong_apply": strong_apply,
    "worth_considering": worth_considering,
    "top_20": top_20,
    "top_10": top_10
}

# Count product roles
product_count = 0
for j in evaluated:
    t = j["title"].lower()
    if any(kw in t for kw in ["product manager", "product analyst", "product owner", "product designer", "associate product", "senior product", "principal product", "staff product", "technical product manager", "digital product", "product lead"]):
        product_count += 1

output["evaluation_summary"]["product_roles"] = product_count
output["evaluation_summary"]["non_product_roles"] = 196 - product_count
output["evaluation_summary"]["india_roles"] = len([j for j in evaluated if "india" in j["location"].lower()])

with open('14-JOB-EVALUATION.json', 'w') as f:
    json.dump(output, f, indent=2, default=str)

print("Evaluation complete!")
print(f"Total evaluated: {len(evaluated)}")
print(f"A: {len(strong_apply)}")
print(f"B: {len(worth_considering)}")
print(f"C: {len([j for j in evaluated if j['category'] == 'C'])}")
print(f"D: {len([j for j in evaluated if j['category'] == 'D'])}")
print(f"Product roles: {product_count}")
print(f"Average score: {output['evaluation_summary']['average_score']}")
print(f"Median score: {output['evaluation_summary']['median_score']}")
print(f"Top 10 count: {len(top_10)}")
print(f"Top 20 count: {len(top_20)}")