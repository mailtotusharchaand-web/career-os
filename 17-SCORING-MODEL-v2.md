# Career OS — Scoring Model v2: Hard Gates + Soft Score

**Version:** 0.1  
**Date:** 2026-08-16  
**Status:** Draft — Replaces ad-hoc weighted scoring in evaluation script

---

## 1. Problem with Current Scoring

The current evaluation uses a single weighted score:

```
overall = 0.15*role + 0.20*seniority + 0.25*domain + 0.15*experience + 0.15*skill + 0.10*location
```

**Failure mode:** A "Compliance Analyst" (non-Product role) scores 76 because:
- domain_fit = 95 (Compliance = primary domain)
- seniority_fit = 90 (Associate level)
- location_fit = 60 (US on-site)
- But role_fit = 10 (not a Product role)

The weighted sum (0.15*10 + 0.20*90 + 0.25*95 + ...) = 76 → **Category A**

This is wrong. A non-Product role should never be Category A for a Product candidate.

---

## 2. New Architecture: Hard Gates + Soft Score

```
                    JOB FIT DECISION
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    HARD GATES       SOFT SCORE       CATEGORY
    (Pass/Fail)     (0-100)          (A/B/C/D)
         │               │
         ▼               ▼
    Must pass       Weighted sum
    ALL gates       of soft factors
```

### Hard Gates (Binary — Must Pass ALL)

| Gate | Check | Fail → Category |
|------|-------|-----------------|
| **G1: Product Function** | Is this a Product role? (PM, APM, Product Analyst, Product Owner, Digital PM, Technical PM) | D |
| **G2: Eligibility** | Can candidate legally work? (India remote, US remote, India hybrid, or willing to relocate for primary domain) | D |
| **G3: Seniority Floor** | Not VP/Director/Principal/Staff (unless exceptional domain match) | D |
| **G4: Employment Type** | Full-time or Contract (not internship, part-time, temporary) | D |
| **G5: Recency** | Posted ≤ 30 days ago | D |

### Soft Score Components (Weighted — Only if ALL Gates Pass)

| Factor | Weight | Description |
|--------|--------|-------------|
| **Domain Fit** | 0.30 | Primary domain = 95, Secondary = 70, Adjacent = 50, Other = 20 |
| **Seniority Match** | 0.25 | Associate=95, Mid=85, Senior=70 (if primary domain), VP=30 |
| **Role Specificity** | 0.20 | Exact title match (Product Analyst) = 95, PM = 85, PO = 80, TPM = 70 |
| **Skill Overlap** | 0.15 | Evidence of SQL, Python, API, PEGA, RCA, UAT, stakeholder mgmt |
| **Location/Remote** | 0.10 | India remote=95, US remote=90, India hybrid=80, US on-site (willing)=60, US on-site=30 |

**Soft Score Range:** 0–100  
**Category Thresholds:**
- **A (Strong Apply):** ≥ 80
- **B (Worth Considering):** 60–79
- **C (Weak Match):** 40–59
- **D (Reject):** < 40 OR any Hard Gate fail

---

## 3. Hard Gate Definitions

### G1: Product Function

```python
def is_product_role(title: str) -> bool:
    title_lower = title.lower()
    product_keywords = [
        "product manager", "product analyst", "product owner",
        "associate product", "senior product", "principal product",
        "staff product", "lead product", "group product",
        "digital product", "technical product manager",
        "product management", "product lead"
    ]
    # Exclude false positives
    exclude = [
        "project manager", "program manager", "project lead",
        "delivery manager", "scrum master", "agile coach",
        "product marketing", "product marketing manager",
        "product designer", "product designer", "ux designer",
        "product designer", "product designer"
    ]
    if any(ex in title_lower for ex in exclude):
        return False
    return any(pk in title_lower for pk in product_keywords)
```

**Edge Cases:**
- "Technical Product Manager" → **PASS** (Product function + technical depth)
- "Product Marketing Manager" → **FAIL** (Marketing function)
- "Project Manager" → **FAIL** (Delivery function)
- "Product Designer" → **FAIL** (Design function)
- "Product Operations" → **FAIL** (Ops function)
- "Product Support" → **FAIL** (Support function)

### G2: Eligibility

| Candidate Location | Job Location | Job Remote | Eligible? |
|-------------------|--------------|------------|-----------|
| Gurugram, India | Any India | Any | ✅ |
| Gurugram, India | India | Remote/Hybrid | ✅ |
| Gurugram, India | US/Global | Remote | ✅ |
| Gurugram, India | US | On-site | ⚠️ Only if willing to relocate AND primary domain |
| Gurugram, India | US | Hybrid | ❌ |
| Gurugram, India | Other country | Remote | ✅ (international remote) |
| Gurugram, India | Other country | On-site | ❌ |

**Implementation:**
```python
def check_eligibility(job_location: str, job_remote: bool, domain: str) -> bool:
    loc = job_location.lower()
    is_india = any(x in loc for x in ["india", "gurugram", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "noida", "chennai"])
    is_us = any(x in loc for x in ["us", "united states", "usa", "remote, us"])
    
    if is_india:
        return True  # India roles always eligible
    if is_us and job_remote:
        return True  # US remote eligible
    if is_us and not job_remote:
        # Only if willing to relocate for primary domain
        return domain in PRIMARY_DOMAINS
    return True  # International remote default eligible
```

### G3: Seniority Floor

```python
def check_seniority_floor(title: str, domain: str) -> bool:
    title_lower = title.lower()
    if any(x in title_lower for x in ["vp", "vice president", "director", "principal", "staff", "head of", "dvp", "avp"]):
        # Exception: primary domain + willing to relocate
        if domain in PRIMARY_DOMAINS:
            return True  # Allow stretch for perfect domain
        return False
    return True
```

### G4: Employment Type

```python
def check_employment_type(job_type: str, title: str) -> bool:
    title_lower = title.lower()
    job_type_lower = (job_type or "").lower()
    
    exclude_terms = ["intern", "trainee", "co-op", "apprentice", "part-time", "part time", "temporary", "temp ", "contract-to-hire"]
    
    if any(term in title_lower for term in exclude_terms):
        return False
    if any(term in job_type_lower for term in ["intern", "part-time", "temporary"]):
        return False
    return True
```

### G5: Recency

```python
def check_recency(date_posted: str, max_days: int = 30) -> bool:
    if not date_posted:
        return True  # Unknown date → don't penalize
    try:
        posted = parse_date(date_posted)
        return (now - posted).days <= max_days
    except:
        return True
```

---

## 4. Soft Score Calculation (Only if All Gates Pass)

```python
def calculate_soft_score(job: dict, candidate: dict) -> dict:
    """
    Returns: {score: int, breakdown: {...}, category: str}
    """
    # Only called if all hard gates pass
    
    # Domain Fit (30%)
    domain = job.get("domain", "Unknown")
    if domain in PRIMARY_DOMAINS:
        domain_fit = 95
    elif domain in SECONDARY_DOMAINS:
        domain_fit = 70
    elif domain in ADJACENT_DOMAINS:
        domain_fit = 50
    else:
        domain_fit = 20
    
    # Seniority Match (25%)
    seniority = classify_seniority(job["title"])
    if seniority == "Associate":
        seniority_match = 95
    elif seniority == "Mid-level":
        seniority_match = 85
    elif seniority == "Senior/Lead/Manager":
        seniority_match = 70 if job["domain"] in PRIMARY_DOMAINS else 50
    elif seniority == "VP/Director/Principal/Staff":
        seniority_match = 30
    else:
        seniority_match = 60
    
    # Role Specificity (20%)
    title = job["title"].lower()
    if "product analyst" in title:
        role_spec = 95
    elif "associate product manager" in title:
        role_spec = 90
    elif "product manager" in title and "senior" not in title:
        role_spec = 85
    elif "product owner" in title:
        role_spec = 80
    elif "technical product manager" in title:
        role_spec = 70
    elif "digital product manager" in title:
        role_spec = 75
    elif "product" in title and "manager" in title:
        role_spec = 65
    else:
        role_spec = 40
    
    # Skill Overlap (15%)
    skill_overlap = calculate_skill_overlap(job["description"])
    
    # Location/Remote (10%)
    location_fit = calculate_location_fit(job)
    
    # Weighted sum
    score = int(
        domain_fit * 0.30 +
        seniority_match * 0.25 +
        role_spec * 0.20 +
        skill_overlap * 0.15 +
        location_fit * 0.10
    )
    
    return {
        "score": min(100, max(0, score)),
        "breakdown": {
            "domain_fit": domain_fit,
            "seniority_match": seniority_match,
            "role_specificity": role_spec,
            "skill_overlap": skill_overlap,
            "location_fit": location_fit
        }
    }
```

---

## 5. Complete Decision Function

```python
def evaluate_job(job: dict, candidate: dict) -> dict:
    """
    Complete evaluation: Hard Gates → Soft Score → Category
    """
    # Hard Gates
    gates = {
        "product_function": is_product_role(job["title"]),
        "eligibility": check_eligibility(job["location"], job.get("is_remote", False), job.get("domain", "")),
        "seniority_floor": check_seniority_floor(job["title"], job.get("domain", "")),
        "employment_type": check_employment_type(job.get("job_type", ""), job["title"]),
        "recency": check_recency(job.get("date_posted", ""))
    }
    
    gate_failures = [k for k, v in gates.items() if not v]
    
    if gate_failures:
        return {
            "overall_score": 0,
            "category": "D",
            "hard_gates": gates,
            "failed_gates": gate_failures,
            "soft_score": None,
            "breakdown": None,
            "recommendation": f"Reject — Hard gate failure: {', '.join(gate_failures)}"
        }
    
    # All gates passed → Soft Score
    soft = calculate_soft_score(job, candidate)
    score = soft["score"]
    
    if score >= 80:
        category = "A"
    elif score >= 60:
        category = "B"
    elif score >= 40:
        category = "C"
    else:
        category = "D"
    
    return {
        "overall_score": score,
        "category": category,
        "hard_gates": gates,
        "failed_gates": [],
        "soft_score": score,
        "breakdown": soft["breakdown"],
        "recommendation": generate_recommendation(category, score, job)
    }
```

---

## 6. Expected Impact on Current Results

### Current (v1) vs New (v2) on Tier 1 Jobs

| Job | v1 Score | v1 Cat | v2 Gates | v2 Score | v2 Cat |
|-----|----------|--------|----------|----------|--------|
| Grand Bank Compliance Analyst | 76 | A | ❌ G1 (not Product) | N/A | **D** |
| Compliance Due Diligence Analyst | 76 | A | ❌ G1 (not Product) | N/A | **D** |
| TransUnion Senior PM Case Mgmt | 75 | A | ✅ All pass | ~82 | **A** |
| Eli Lilly Identity Product Owner | 79 | A | ✅ All pass | ~79 | **A** |
| Stripe PM Ecosystem Risk | 72 | B | ✅ All pass | ~78 | **B** |
| Stripe PM Compliance | 72 | B | ✅ All pass | ~78 | **B** |
| Risk & Third-Party Specialist | 72 | B | ❌ G1 (not Product) | N/A | **D** |
| Crowe Financial Crime (14×) | 69 | B | ❌ G1 (not Product) | N/A | **D** |
| Five Below Support Lead (14×) | N/A | D | ❌ G1, G4 | N/A | **D** |
| Data Analyst roles | 55-68 | B/C | ❌ G1 | N/A | **D** |
| Senior PM/VP roles (OKX, Capital One, etc.) | 69 | B | ❌ G3 | N/A | **D** |

**Expected Distribution (v2):**
| Category | Expected Count |
|----------|----------------|
| A | 3-5 |
| B | 15-25 |
| C | 30-40 |
| D | 120-140 |

---

## 7. Implementation Plan

### Files to Modify

| File | Change |
|------|--------|
| `evaluate_all_v2.py` | Replace scoring logic with `evaluate_job()` |
| `scout.py` | Add `is_product_role()` check in deterministic filters (optional — gate at eval time) |

### New Files

| File | Purpose |
|------|---------|
| `career_os/scoring/gates.py` | Hard gate implementations |
| `career_os/scoring/soft_score.py` | Soft score calculation |
| `career_os/scoring/evaluator.py` | Main `evaluate_job()` function |
| `career_os/scoring/config.py` | Domain lists, weights, thresholds |

---

## 8. Configuration

```yaml
# config/scoring.yaml
hard_gates:
  product_function:
    enabled: true
    exclude_keywords:
      - "project manager"
      - "program manager"
      - "project lead"
      - "delivery manager"
      - "scrum master"
      - "agile coach"
      - "product marketing"
      - "product designer"
      - "product operations"
      - "product support"
  
  eligibility:
    enabled: true
    willing_to_relocate_for_primary: true
  
  seniority_floor:
    enabled: true
    allow_vp_for_primary_domain: true
  
  employment_type:
    enabled: true
    exclude:
      - "intern"
      - "trainee"
      - "co-op"
      - "part-time"
      - "temporary"
  
  recency:
    enabled: true
    max_days: 30

soft_score:
  weights:
    domain_fit: 0.30
    seniority_match: 0.25
    role_specificity: 0.20
    skill_overlap: 0.15
    location_fit: 0.10
  
  domain_values:
    primary: 95
    secondary: 70
    adjacent: 50
    other: 20
  
  seniority_values:
    associate: 95
    mid: 85
    senior: 70
    vp_director: 30
  
  role_specificity:
    product_analyst: 95
    associate_pm: 90
    product_manager: 85
    product_owner: 80
    digital_pm: 75
    technical_pm: 70
    other_product: 65
  
  location_values:
    india_remote: 95
    us_remote: 90
    india_hybrid: 80
    us_onsite_willing: 60
    us_onsite: 30

thresholds:
  A: 80
  B: 60
  C: 40
  D: 0
```

---

## 9. Test Cases

```python
def test_hard_gates():
    # Product role → pass
    assert is_product_role("Product Manager") == True
    assert is_product_role("Associate Product Manager") == True
    assert is_product_role("Product Analyst") == True
    assert is_product_role("Product Owner") == True
    assert is_product_role("Digital Product Manager") == True
    assert is_product_role("Technical Product Manager") == True
    
    # Non-product → fail
    assert is_product_role("Project Manager") == False
    assert is_product_role("Program Manager") == False
    assert is_product_role("Product Marketing Manager") == False
    assert is_product_role("Product Designer") == False
    assert is_product_role("Software Engineer") == False
    assert is_product_role("Data Analyst") == False
    assert is_product_role("Compliance Analyst") == False
    assert is_product_role("Customer Success Manager") == False
    
    # Seniority floor
    assert check_seniority_floor("Product Manager", "Payments") == True
    assert check_seniority_floor("VP Product", "Payments") == True  # primary domain exception
    assert check_seniority_floor("VP Product", "Marketing") == False
    assert check_seniority_floor("Director Product", "KYC") == True
    assert check_seniority_floor("Director Product", "HR") == False
    
    # Employment type
    assert check_employment_type("fulltime", "Product Manager") == True
    assert check_employment_type("", "Product Manager Intern") == False
    assert check_employment_type("part-time", "Product Manager") == False
    
    print("All tests passed!")
```

---

## 10. Migration Checklist

- [ ] Create `career_os/scoring/` module
- [ ] Implement `gates.py`, `soft_score.py`, `evaluator.py`
- [ ] Add `config/scoring.yaml`
- [ ] Update `evaluate_all_v2.py` to use new evaluator
- [ ] Run test suite
- [ ] Re-evaluate Tier 1 jobs with v2 model
- [ ] Verify TransUnion Senior PM stays A
- [ ] Verify Compliance Analysts become D
- [ ] Verify Crowe/Five Below become D
- [ ] Run Tier 2 queries with new model
- [ ] Document in `13-SEARCH-STRATEGY.md` update

---

## 11. Success Criteria

| Metric | Target |
|--------|--------|
| Zero non-Product roles in Category A | 100% |
| Zero non-Product roles in Category B | 90%+ |
| TransUnion Senior PM (Case Mgmt) remains A | ✅ |
| Stripe PM roles remain B+ | ✅ |
| Crowe/Five Below/retail all D | ✅ |
| Senior PM/VP stretch roles appropriately C/D | ✅ |
| India-remote Product roles get location boost | ✅ |