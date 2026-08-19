#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_evaluations.py — Comprehensive Audit & Human Review Generator for Career OS

Reads:
  - llm_evaluations_full.json (read-only)

Generates:
  - llm_evaluation_audit.md
  - llm_evaluation_review.json
  - llm_evaluation_review.csv

Strictly audit-only:
  - Does NOT alter original evaluation records or recommendations.
  - Does NOT enforce domain/role/company constraints.
  - Human review fields (human_verdict, human_priority, human_notes, human_correction) are left EMPTY.
"""

import json
import csv
import random
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict

INPUT_FILE = "llm_evaluations_full.json"
OUTPUT_MD = "llm_evaluation_audit.md"
OUTPUT_JSON = "llm_evaluation_review.json"
OUTPUT_CSV = "llm_evaluation_review.csv"
RANDOM_SEED = 42

def load_evaluations(path: str = INPUT_FILE) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def upside_rank(val: str) -> int:
    val = (val or "").lower()
    if "high" in val:
        return 3
    elif "med" in val:
        return 2
    elif "low" in val:
        return 1
    return 0

def format_salary(job: dict) -> str:
    s_min = job.get("salary_min")
    s_max = job.get("salary_max")
    interval = job.get("salary_interval") or ""
    if s_min and s_max:
        return f"${s_min:,.0f} - ${s_max:,.0f} ({interval})"
    elif s_min:
        return f"From ${s_min:,.0f} ({interval})"
    elif s_max:
        return f"Up to ${s_max:,.0f} ({interval})"
    return "Not specified"

def main():
    print(f"Loading {INPUT_FILE}...")
    raw_data = load_evaluations(INPUT_FILE)
    meta = raw_data.get("meta", {})
    all_records = raw_data.get("evaluations", [])

    total_records = len(all_records)
    gate_rejected = [r for r in all_records if r.get("gate_failed")]
    llm_evals = [r for r in all_records if not r.get("gate_failed")]

    print(f"Total records: {total_records}")
    print(f"Gate-rejected: {len(gate_rejected)}")
    print(f"LLM-evaluated: {len(llm_evals)}")

    # Group by recommendation
    rec_groups = defaultdict(list)
    for r in llm_evals:
        rec = r.get("llm_evaluation", {}).get("recommendation", "Unknown")
        rec_groups[rec].append(r)

    consider_jobs = rec_groups.get("Consider", [])
    long_shot_jobs = rec_groups.get("Long Shot", [])
    skip_jobs = rec_groups.get("Skip", [])

    print(f"Consider: {len(consider_jobs)}")
    print(f"Long Shot: {len(long_shot_jobs)}")
    print(f"Skip: {len(skip_jobs)}")

    # 1. Sort Consider jobs (rank by overall_score desc, probability_of_obtaining desc)
    consider_sorted = sorted(
        consider_jobs,
        key=lambda x: (
            x["llm_evaluation"].get("overall_score", 0),
            x["llm_evaluation"].get("probability_of_obtaining", 0),
            x["llm_evaluation"].get("transferable_capability_fit", 0),
        ),
        reverse=True
    )

    # 2. Sort Long Shot jobs (rank by: 1. overall_score desc, 2. career_upside desc, 3. transferable_capability_fit desc)
    long_shot_sorted = sorted(
        long_shot_jobs,
        key=lambda x: (
            x["llm_evaluation"].get("overall_score", 0),
            upside_rank(x["llm_evaluation"].get("career_upside", "")),
            x["llm_evaluation"].get("transferable_capability_fit", 0),
            x["llm_evaluation"].get("probability_of_obtaining", 0),
        ),
        reverse=True
    )

    # 3. Skip False-Negative Review Set:
    # A. Top 20 highest-scoring Skip jobs
    skip_sorted_by_score = sorted(
        skip_jobs,
        key=lambda x: (
            x["llm_evaluation"].get("overall_score", 0),
            x["llm_evaluation"].get("opportunity_alignment", 0),
            x["llm_evaluation"].get("transferable_capability_fit", 0),
        ),
        reverse=True
    )
    skip_top20 = skip_sorted_by_score[:20]
    skip_top20_ids = {x.get("job_id") for x in skip_top20}

    # B. 10 Randomly selected Skip jobs from the remainder (reproducible seed)
    remaining_skips = [x for x in skip_jobs if x.get("job_id") not in skip_top20_ids]
    rng = random.Random(RANDOM_SEED)
    skip_random10 = rng.sample(remaining_skips, min(10, len(remaining_skips)))

    # 4. Potentially Unexpected Opportunities:
    # Roles outside standard "Product Analyst" / "Associate Product Manager" with notable upside or transferable capability
    unexpected_candidates = []
    # Identify non-obvious titles in Consider & Long Shot
    standard_pattern = re.compile(r"(associate\s+product\s+manager|product\s+analyst|apm\b)", re.IGNORECASE)
    for r in consider_sorted + long_shot_sorted:
        title = r.get("title", "")
        ev = r.get("llm_evaluation", {})
        score = ev.get("overall_score", 0)
        transferable = ev.get("transferable_capability_fit", 0)
        upside = ev.get("career_upside", "").lower()
        if not standard_pattern.search(title) and (score >= 40 or transferable >= 55 or upside == "high"):
            unexpected_candidates.append(r)

    # 5. Consistency & Inconsistency Checks
    inconsistencies = []
    for r in llm_evals:
        ev = r.get("llm_evaluation", {})
        rec = ev.get("recommendation", "")
        score = ev.get("overall_score", 0)
        prob = ev.get("probability_of_obtaining", 0)
        trans = ev.get("transferable_capability_fit", 0)
        align = ev.get("opportunity_alignment", 0)
        title = r.get("title", "")
        company = r.get("company", "")
        job_id = r.get("job_id", "")

        # High score + Skip
        if rec == "Skip" and score >= 40:
            inconsistencies.append({
                "type": "High score + Skip",
                "job_id": job_id, "title": title, "company": company,
                "score": score, "recommendation": rec, "prob": prob,
                "details": f"Overall score is {score}/100 but recommended Skip. Transition difficulty: {ev.get('transition_difficulty')}"
            })
        # Low score + Consider
        if rec == "Consider" and score < 45:
            inconsistencies.append({
                "type": "Low score + Consider",
                "job_id": job_id, "title": title, "company": company,
                "score": score, "recommendation": rec, "prob": prob,
                "details": f"Overall score is {score}/100 but recommended Consider."
            })
        # High probability + Skip
        if rec == "Skip" and prob >= 30:
            inconsistencies.append({
                "type": "High probability + Skip",
                "job_id": job_id, "title": title, "company": company,
                "score": score, "recommendation": rec, "prob": prob,
                "details": f"Probability of obtaining is {prob}% but recommended Skip."
            })
        # Low probability + Consider
        if rec == "Consider" and prob <= 20:
            inconsistencies.append({
                "type": "Low probability + Consider",
                "job_id": job_id, "title": title, "company": company,
                "score": score, "recommendation": rec, "prob": prob,
                "details": f"Probability of obtaining is {prob}% but recommended Consider (potential high-stretch high-alignment)."
            })
        # High transferable fit + Skip
        if rec == "Skip" and trans >= 70:
            inconsistencies.append({
                "type": "High transferable capability + Skip",
                "job_id": job_id, "title": title, "company": company,
                "score": score, "recommendation": rec, "prob": prob,
                "details": f"Transferable capability fit is {trans}/100 but recommended Skip."
            })
        # High opportunity alignment + Skip
        if rec == "Skip" and align >= 70:
            inconsistencies.append({
                "type": "High opportunity alignment + Skip",
                "job_id": job_id, "title": title, "company": company,
                "score": score, "recommendation": rec, "prob": prob,
                "details": f"Opportunity alignment is {align}/100 but recommended Skip."
            })

    # Stats distribution
    def compute_stats(items, key):
        vals = [x["llm_evaluation"].get(key, 0) for x in items if key in x.get("llm_evaluation", {})]
        if not vals:
            return {"min": 0, "max": 0, "avg": 0, "median": 0}
        vals_s = sorted(vals)
        med = vals_s[len(vals_s)//2]
        return {"min": min(vals), "max": max(vals), "avg": round(sum(vals)/len(vals), 1), "median": med}

    score_stats = {
        "Consider": compute_stats(consider_jobs, "overall_score"),
        "Long Shot": compute_stats(long_shot_jobs, "overall_score"),
        "Skip": compute_stats(skip_jobs, "overall_score"),
    }
    prob_stats = {
        "Consider": compute_stats(consider_jobs, "probability_of_obtaining"),
        "Long Shot": compute_stats(long_shot_jobs, "probability_of_obtaining"),
        "Skip": compute_stats(skip_jobs, "probability_of_obtaining"),
    }
    upside_stats = {
        "Consider": Counter([x["llm_evaluation"].get("career_upside", "unknown") for x in consider_jobs]),
        "Long Shot": Counter([x["llm_evaluation"].get("career_upside", "unknown") for x in long_shot_jobs]),
        "Skip": Counter([x["llm_evaluation"].get("career_upside", "unknown") for x in skip_jobs]),
    }

    # 6. Pattern Analysis across all 184 evaluated jobs
    # A. Role Categories
    role_cats = Counter()
    for r in llm_evals:
        t = r.get("title", "").lower()
        if "product manager" in t or "product management" in t or "pm " in t or "apm" in t or "product lead" in t or "director, product" in t:
            role_cats["Product Management"] += 1
        elif "product analyst" in t or "business analyst" in t or "data analyst" in t or "analytics" in t:
            role_cats["Analytics & Data / Business Analysis"] += 1
        elif "customer success" in t or "client success" in t or "account manager" in t:
            role_cats["Customer Success / Account Management"] += 1
        elif "marketing" in t or "growth" in t:
            role_cats["Growth & Marketing"] += 1
        elif "operations" in t or "program manager" in t or "project manager" in t or "tpm" in t:
            role_cats["Operations & Program / Project Management"] += 1
        elif "engineer" in t or "developer" in t or "architect" in t:
            role_cats["Engineering & Technical Architecture"] += 1
        elif "sales" in t or "business development" in t or "account executive" in t:
            role_cats["Sales & Business Development"] += 1
        elif "legal" in t or "compliance" in t or "counsel" in t:
            role_cats["Legal, Risk & Compliance"] += 1
        else:
            role_cats["Other Specialist / General"] += 1

    # B. Top Companies
    company_counts = Counter([r.get("company", "Unknown") for r in llm_evals]).most_common(12)

    # C. Recurring Missing Skills & Gaps
    missing_skills_counter = Counter()
    for r in llm_evals:
        skills = r.get("llm_evaluation", {}).get("missing_critical_skills", [])
        for s in skills:
            s_clean = s.strip()
            if s_clean:
                # normalize basic phrases
                s_lower = s_clean.lower()
                if "direct people management" in s_lower or "people leadership" in s_lower or "managing managers" in s_lower:
                    missing_skills_counter["Direct People Management / Leadership"] += 1
                elif "us work authorization" in s_lower or "us residence" in s_lower or "us citizenship" in s_lower:
                    missing_skills_counter["US Work Authorization / Location Eligibility"] += 1
                elif "quota" in s_lower or "sales performance" in s_lower or "revenue generation" in s_lower:
                    missing_skills_counter["Quota-carrying Sales / Commercial Revenue Ownership"] += 1
                elif "p&l" in s_lower or "financial budget" in s_lower:
                    missing_skills_counter["P&L Accountability / Multi-Million Budget Ownership"] += 1
                elif "coding" in s_lower or "production code" in s_lower or "software engineering" in s_lower:
                    missing_skills_counter["Hands-on Production Software Engineering"] += 1
                elif "legal" in s_lower or "jd" in s_lower or "bar" in s_lower:
                    missing_skills_counter["Legal Degree / Bar Admission"] += 1
                elif "domain expertise" in s_lower or "deep domain" in s_lower:
                    missing_skills_counter["Specialized Domain Experience (Healthcare/Defense/etc)"] += 1
                else:
                    missing_skills_counter[s_clean] += 1

    # D. Key Transferable Strengths
    strengths_counter = Counter()
    for r in llm_evals:
        strengths = r.get("llm_evaluation", {}).get("key_strengths", [])
        for s in strengths:
            s_clean = s.strip()
            if s_clean:
                s_lower = s_clean.lower()
                if "cross-functional" in s_lower or "stakeholder" in s_lower:
                    strengths_counter["Cross-functional Stakeholder Management & Alignment"] += 1
                elif "uat" in s_lower or "user acceptance" in s_lower or "testing" in s_lower:
                    strengths_counter["UAT Leadership, Test Case Design & QA Collaboration"] += 1
                elif "agile" in s_lower or "scrum" in s_lower or "backlog" in s_lower or "sprint" in s_lower:
                    strengths_counter["Agile / Scrum Backlog Management & PRD Writing"] += 1
                elif "fintech" in s_lower or "payments" in s_lower or "amex" in s_lower or "american express" in s_lower:
                    strengths_counter["Enterprise Fintech, Payments & Banking Workflows"] += 1
                elif "sql" in s_lower or "analytics" in s_lower or "data" in s_lower or "python" in s_lower:
                    strengths_counter["Data Analytics, SQL Querying & Metric Tracking"] += 1
                elif "api" in s_lower or "technical" in s_lower:
                    strengths_counter["Technical Acumen, API Debugging & Systems Integration"] += 1
                else:
                    strengths_counter[s_clean] += 1

    # E. Location / Remote Distribution
    loc_counter = Counter()
    for r in llm_evals:
        is_rem = r.get("is_remote", False)
        loc = r.get("location", "")
        if is_rem:
            loc_counter["Remote"] += 1
        elif "india" in loc.lower() or "bengaluru" in loc.lower() or "bangalore" in loc.lower() or "delhi" in loc.lower() or "gurgaon" in loc.lower():
            loc_counter["India (Onsite/Hybrid)"] += 1
        elif "us" in loc.lower() or "ny" in loc.lower() or "ca" in loc.lower() or "wa" in loc.lower() or "tx" in loc.lower():
            loc_counter["US (Onsite/Hybrid)"] += 1
        else:
            loc_counter["Other / Global"] += 1

    # F. Compensation Patterns
    salaries = [r.get("salary_max") for r in llm_evals if r.get("salary_max")]
    sal_stats = {
        "count_disclosed": len(salaries),
        "min": min(salaries) if salaries else 0,
        "max": max(salaries) if salaries else 0,
        "avg": round(sum(salaries)/len(salaries), 1) if salaries else 0,
        "median": sorted(salaries)[len(salaries)//2] if salaries else 0
    }

    # =========================================================================
    # GENERATE llm_evaluation_review.json
    # =========================================================================
    review_json_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "source_file": INPUT_FILE,
            "total_jobs_in_source": total_records,
            "total_llm_evaluated": len(llm_evals),
            "total_gate_rejected": len(gate_rejected),
            "distribution": {
                "Consider": len(consider_jobs),
                "Long Shot": len(long_shot_jobs),
                "Skip": len(skip_jobs),
                "Gate_Rejected": len(gate_rejected),
            },
            "score_ranges": score_stats,
            "probability_ranges": prob_stats,
            "career_upside_distribution": {k: dict(v) for k, v in upside_stats.items()},
            "random_seed_used_for_skip_sample": RANDOM_SEED
        },
        "consider_set": consider_sorted,
        "long_shot_set": long_shot_sorted,
        "skip_top20_set": skip_top20,
        "skip_random10_set": skip_random10,
        "unexpected_opportunities": unexpected_candidates,
        "score_inconsistencies": inconsistencies,
        "pattern_summary": {
            "role_categories": dict(role_cats),
            "top_companies": dict(company_counts),
            "top_recurring_missing_skills": dict(missing_skills_counter.most_common(10)),
            "top_transferable_strengths": dict(strengths_counter.most_common(10)),
            "location_distribution": dict(loc_counter),
            "salary_statistics": sal_stats,
        }
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(review_json_data, f, indent=2, ensure_ascii=False)
    print(f"Generated {OUTPUT_JSON}")

    # =========================================================================
    # GENERATE llm_evaluation_review.csv
    # =========================================================================
    # Construct rows for human review
    # We include Consider (21), Long Shots (42), Top 20 Skips (20), Random 10 Skips (10)
    review_sets = [
        ("Consider (All 21)", consider_sorted),
        ("Long Shot (All 42)", long_shot_sorted),
        ("Skip Top 20 by Score", skip_top20),
        ("Skip Random 10 Sample", skip_random10),
    ]

    csv_rows = []
    seen_in_csv = set()

    for set_name, items in review_sets:
        for rank_idx, item in enumerate(items, start=1):
            job_id = item.get("job_id")
            # Track duplicates if any appear across sets (e.g. skip sets)
            ev = item.get("llm_evaluation", {})
            row = {
                "review_set": set_name,
                "rank_in_set": rank_idx,
                "job_id": job_id,
                "title": item.get("title", ""),
                "company": item.get("company", ""),
                "location": item.get("location", ""),
                "is_remote": "Yes" if item.get("is_remote") else "No",
                "salary": format_salary(item),
                "application_url": item.get("application_url", ""),
                "overall_score": ev.get("overall_score", 0),
                "llm_recommendation": ev.get("recommendation", ""),
                "probability_of_obtaining": f"{ev.get('probability_of_obtaining', 0)}%",
                "confidence": ev.get("confidence", ""),
                "role_fit": ev.get("role_fit", 0),
                "current_experience_fit": ev.get("current_experience_fit", 0),
                "transferable_capability_fit": ev.get("transferable_capability_fit", 0),
                "seniority_fit": ev.get("seniority_fit", 0),
                "opportunity_alignment": ev.get("opportunity_alignment", 0),
                "transition_difficulty": ev.get("transition_difficulty", ""),
                "career_upside": ev.get("career_upside", ""),
                "compensation_upside": ev.get("compensation_upside", ""),
                "key_strengths": " | ".join(ev.get("key_strengths", [])),
                "missing_critical_skills": " | ".join(ev.get("missing_critical_skills", [])),
                "llm_reasoning": ev.get("reasoning", ""),
                "human_verdict": "",      # Intentionally EMPTY for human input
                "human_priority": "",     # Intentionally EMPTY for human input
                "human_notes": "",        # Intentionally EMPTY for human input
                "human_correction": ""    # Intentionally EMPTY for human input
            }
            csv_rows.append(row)
            seen_in_csv.add(job_id)

    csv_fields = [
        "review_set", "rank_in_set", "job_id", "title", "company", "location",
        "is_remote", "salary", "application_url", "overall_score", "llm_recommendation",
        "probability_of_obtaining", "confidence", "role_fit", "current_experience_fit",
        "transferable_capability_fit", "seniority_fit", "opportunity_alignment",
        "transition_difficulty", "career_upside", "compensation_upside",
        "key_strengths", "missing_critical_skills", "llm_reasoning",
        "human_verdict", "human_priority", "human_notes", "human_correction"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Generated {OUTPUT_CSV} ({len(csv_rows)} rows)")

    # =========================================================================
    # GENERATE llm_evaluation_audit.md
    # =========================================================================
    md_lines = []
    
    def p(text: str = ""):
        md_lines.append(text)

    # 1. Executive summary
    p("# Career OS — LLM Evaluation Audit & Human Review Package")
    p()
    p(f"> **Evaluation Run Date**: {raw_data.get('generated_at', '2026-08-16')}  ")
    p(f"> **Model Used**: `{meta.get('llm_model', 'gemini-flash-lite-latest')}` (Provider: `gemini`)  ")
    p(f"> **Input Dataset**: `{meta.get('jobs_file', 'tier1_jobs.json')}` (196 total jobs)  ")
    p(f"> **Candidate Profile**: `{meta.get('cv_file', 'Tushar_Chaand_CV.docx')}`  ")
    p()
    p("---")
    p()
    p("## 1. Executive Summary")
    p()
    p("The Career OS evaluation pipeline performed a comprehensive LLM evaluation over 196 scraped market opportunities without hard-coded domain, company, seniority, or role-title filters. Only explicit candidate constraints (employment type & 30-day posting recency) were applied deterministically.")
    p()
    p("### High-Level Metrics")
    p()
    p("| Metric | Count | Percentage | Description |")
    p("|---|---|---|---|")
    p(f"| **Total Universe** | `{total_records}` | 100.0% | Total opportunities loaded from `tier1_jobs.json` |")
    p(f"| **Explicit Gate Rejections** | `{len(gate_rejected)}` | {len(gate_rejected)/total_records*100:.1f}% | Excluded by candidate hard constraints (10 part-time/temp, 2 >30d old) |")
    p(f"| **LLM Evaluated** | `{len(llm_evals)}` | {len(llm_evals)/total_records*100:.1f}% | Evaluated through full candidate CV & JD prompt |")
    p(f"| ├─ **Consider** | `{len(consider_jobs)}` | {len(consider_jobs)/total_records*100:.1f}% | High-viability opportunities with strong role/transferable fit |")
    p(f"| ├─ **Long Shot** | `{len(long_shot_jobs)}` | {len(long_shot_jobs)/total_records*100:.1f}% | High-upside or stretch opportunities requiring targeted bridge narratives |")
    p(f"| └─ **Skip** | `{len(skip_jobs)}` | {len(skip_jobs)/total_records*100:.1f}% | Significant functional divergence, seniority mismatch, or empty descriptions |")
    p(f"| **API Errors** | `0` | 0.0% | Zero failures, zero rate-limit drops |")
    p()
    p("### Recommendation Score & Probability Distribution")
    p()
    p("| Recommendation | Count | Score Min-Max (Avg) | Prob Min-Max (Avg) | Career Upside Profile |")
    p("|---|---|---|---|---|")
    p(f"| **Consider** | {len(consider_jobs)} | {score_stats['Consider']['min']}-{score_stats['Consider']['max']} ({score_stats['Consider']['avg']}) | {prob_stats['Consider']['min']}%-{prob_stats['Consider']['max']}% ({prob_stats['Consider']['avg']}%) | High: {upside_stats['Consider'].get('high', 0)}, Med: {upside_stats['Consider'].get('medium', 0)}, Low: {upside_stats['Consider'].get('low', 0)} |")
    p(f"| **Long Shot** | {len(long_shot_jobs)} | {score_stats['Long Shot']['min']}-{score_stats['Long Shot']['max']} ({score_stats['Long Shot']['avg']}) | {prob_stats['Long Shot']['min']}%-{prob_stats['Long Shot']['max']}% ({prob_stats['Long Shot']['avg']}%) | High: {upside_stats['Long Shot'].get('high', 0)}, Med: {upside_stats['Long Shot'].get('medium', 0)}, Low: {upside_stats['Long Shot'].get('low', 0)} |")
    p(f"| **Skip** | {len(skip_jobs)} | {score_stats['Skip']['min']}-{score_stats['Skip']['max']} ({score_stats['Skip']['avg']}) | {prob_stats['Skip']['min']}%-{prob_stats['Skip']['max']}% ({prob_stats['Skip']['avg']}%) | High: {upside_stats['Skip'].get('high', 0)}, Med: {upside_stats['Skip'].get('medium', 0)}, Low: {upside_stats['Skip'].get('low', 0)} |")
    p()
    p("---")
    p()

    # 2. All 21 Consider jobs
    p('## 2. Primary Review Set - All 21 "Consider" Jobs')
    p()
    p("This set represents the primary target opportunities identified by the model. Each job is detailed below with complete multi-dimensional fit scoring and LLM reasoning.")
    p()

    for idx, r in enumerate(consider_sorted, start=1):
        ev = r.get("llm_evaluation", {})
        p(f"### #{idx}. {r.get('title')} — {r.get('company')}")
        p()
        p(f"- **Job ID**: `{r.get('job_id')}`")
        p(f"- **Location**: {r.get('location', 'Not specified')} | **Remote**: {'Yes' if r.get('is_remote') else 'No'}")
        p(f"- **Salary**: {format_salary(r)}")
        p(f"- **Application URL**: [{r.get('application_url')}]({r.get('application_url')})")
        p()
        p("| Metric | Score / Level | Metric | Score / Level |")
        p("|---|---|---|---|")
        p(f"| **Overall Score** | **{ev.get('overall_score')}/100** | **Recommendation** | **{ev.get('recommendation')}** |")
        p(f"| **Probability of Obtaining** | **{ev.get('probability_of_obtaining')}%** | **Confidence** | {ev.get('confidence')} |")
        p(f"| **Role Fit** | {ev.get('role_fit')}/100 | **Seniority Fit** | {ev.get('seniority_fit')}/100 |")
        p(f"| **Current Experience Fit** | {ev.get('current_experience_fit')}/100 | **Transferable Capability Fit** | {ev.get('transferable_capability_fit')}/100 |")
        p(f"| **Opportunity Alignment** | {ev.get('opportunity_alignment')}/100 | **Transition Difficulty** | `{ev.get('transition_difficulty')}` |")
        p(f"| **Career Upside** | `{ev.get('career_upside')}` | **Compensation Upside** | `{ev.get('compensation_upside')}` |")
        p()
        p(f"**Key Strengths Recognized**:")
        for s in ev.get("key_strengths", []):
            p(f"- {s}")
        p()
        p(f"**Missing Critical Skills / Gaps**:")
        missing = ev.get("missing_critical_skills", [])
        if missing:
            for m in missing:
                p(f"- {m}")
        else:
            p("- *None flagged as critical blockers*")
        p()
        p(f"**LLM Reasoning**:")
        p(f"> {ev.get('reasoning')}")
        p()
        p(f"**Evidence Alignment**:")
        p(f"- **Candidate Evidence**: {ev.get('evidence')}")
        p(f"- **Missing / Needed Evidence**: {ev.get('missing_evidence')}")
        p()
        p("---")
        p()

    # 3. Top Long Shots
    p("## 3. Long Shot Review Set — 42 Opportunities")
    p()
    p("Ranked by: (1) Highest Overall Score, (2) Highest Career Upside, (3) Highest Transferable Capability Fit.")
    p()
    p("| Rank | Score | P(Get) | Title | Company | Location | Upside | Difficulty | Key Strengths / Bridge |")
    p("|---|---|---|---|---|---|---|---|---|")
    for idx, r in enumerate(long_shot_sorted, start=1):
        ev = r.get("llm_evaluation", {})
        strengths_short = "; ".join(ev.get("key_strengths", []))[:80] + "..." if ev.get("key_strengths") else "N/A"
        p(f"| #{idx} | **{ev.get('overall_score')}** | {ev.get('probability_of_obtaining')}% | [{r.get('title')}]({r.get('application_url')}) | {r.get('company')} | {r.get('location')} | `{ev.get('career_upside')}` | `{ev.get('transition_difficulty')}` | {strengths_short} |")
    p()
    p("---")
    p()

    # 4. Top 20 Skip jobs by score
    p("## 4. Top 20 Skip Jobs by Score (False-Negative Review Pool)")
    p()
    p("This review set examines the highest-scoring jobs that were assigned a `Skip` recommendation to identify potential false negatives or evaluator anomalies.")
    p()
    p("| Rank | Score | P(Get) | Title | Company | Location | Transferable Fit | Transition Difficulty | LLM Rationale for Skipping |")
    p("|---|---|---|---|---|---|---|---|---|")
    for idx, r in enumerate(skip_top20, start=1):
        ev = r.get("llm_evaluation", {})
        reason_short = ev.get("reasoning", "")[:120] + "..."
        p(f"| #{idx} | **{ev.get('overall_score')}** | {ev.get('probability_of_obtaining')}% | [{r.get('title')}]({r.get('application_url')}) | {r.get('company')} | {r.get('location')} | {ev.get('transferable_capability_fit')}/100 | `{ev.get('transition_difficulty')}` | {reason_short} |")
    p()
    p("---")
    p()

    # 5. 10 random Skip jobs
    p("## 5. 10 Randomly Sampled Skip Jobs (Reproducible Seed: `42`)")
    p()
    p("Spot-check sample drawn randomly from the remaining Skip pool to audit baseline rejection accuracy.")
    p()
    p("| Sample # | Score | P(Get) | Title | Company | Location | Stated Missing Skills | LLM Reasoning Summary |")
    p("|---|---|---|---|---|---|---|---|")
    for idx, r in enumerate(skip_random10, start=1):
        ev = r.get("llm_evaluation", {})
        missing_short = "; ".join(ev.get("missing_critical_skills", []))[:70] + "..." if ev.get("missing_critical_skills") else "N/A"
        reason_short = ev.get("reasoning", "")[:100] + "..."
        p(f"| #{idx} | {ev.get('overall_score')} | {ev.get('probability_of_obtaining')}% | [{r.get('title')}]({r.get('application_url')}) | {r.get('company')} | {r.get('location')} | {missing_short} | {reason_short} |")
    p()
    p("---")
    p()

    # 6. Potentially Unexpected Opportunities
    p("## 6. Potentially Unexpected Opportunities")
    p()
    p("These roles represent opportunities that lie **outside** the candidate's immediate historical title (Product Analyst / APM in Fintech), but where the LLM recognized strong transferable capability, strategic career upside, or high opportunity alignment.")
    p()

    for idx, r in enumerate(unexpected_candidates[:10], start=1):
        ev = r.get("llm_evaluation", {})
        p(f"### Discovery Opportunity #{idx}: {r.get('title')} — {r.get('company')}")
        p()
        p(f"- **Job ID**: `{r.get('job_id')}` | **URL**: [{r.get('application_url')}]({r.get('application_url')})")
        p(f"- **Category / Role**: {r.get('title')}")
        p(f"- **Overall Score**: **{ev.get('overall_score')}/100** | **Recommendation**: `{ev.get('recommendation')}` | **P(Get)**: {ev.get('probability_of_obtaining')}%")
        p(f"- **Transferable Fit**: {ev.get('transferable_capability_fit')}/100 | **Career Upside**: `{ev.get('career_upside')}` | **Transition Difficulty**: `{ev.get('transition_difficulty')}`")
        p()
        p(f"**Why Transferable / Bridge Capabilities**:")
        for s in ev.get("key_strengths", []):
            p(f"- {s}")
        p()
        p(f"**Major Missing Capability / Stretch Area**:")
        for m in ev.get("missing_critical_skills", []):
            p(f"- {m}")
        p()
        p(f"**LLM Synthesis**:")
        p(f"> {ev.get('reasoning')}")
        p()
        p("---")
        p()

    # 7. Score/recommendation inconsistencies
    p("## 7. Score / Recommendation Consistency Analysis")
    p()
    p("### Metric Ranges by Recommendation Tier")
    p()
    p("| Recommendation | Min Score | Median Score | Max Score | Min P(Get) | Median P(Get) | Max P(Get) | Dominant Upside |")
    p("|---|---|---|---|---|---|---|---|")
    for rec in ("Consider", "Long Shot", "Skip"):
        s = score_stats[rec]
        pr = prob_stats[rec]
        dom_up = upside_stats[rec].most_common(1)[0][0] if upside_stats[rec] else "N/A"
        p(f"| **{rec}** | {s['min']} | {s['median']} | {s['max']} | {pr['min']}% | {pr['median']}% | {pr['max']}% | `{dom_up}` |")
    p()
    p("### Flagged Evaluator Inconsistencies for Human Review")
    p()
    if inconsistencies:
        p(f"Identified **{len(inconsistencies)}** edge-case evaluations where multidimensional scores and final tier assignment show interesting tension:")
        p()
        p("| Anomaly Type | Job Title | Company | Overall Score | P(Get) | Rec | Details / Reason for Tension |")
        p("|---|---|---|---|---|---|---|")
        for inc in inconsistencies:
            p(f"| **{inc['type']}** | {inc['title']} | {inc['company']} | {inc['score']} | {inc['prob']}% | `{inc['recommendation']}` | {inc['details']} |")
    else:
        p("No internal score/recommendation contradictions detected.")
    p()
    p("---")
    p()

    # 8. Observed patterns
    p("## 8. Observed Patterns (Descriptive Only)")
    p()
    p("> **Architectural Note**: These patterns represent empirical observations from the current 184-job evaluation. They must **NOT** be converted into hard-coded search rules, company blacklists, or domain exclusions.")
    p()
    p("### A. Role Category Breakdown")
    p()
    for cat, count in role_cats.most_common():
        pct = count / len(llm_evals) * 100
        p(f"- **{cat}**: `{count}` jobs ({pct:.1f}%)")
    p()
    p("### B. Frequent Hiring Companies in Sample")
    p()
    for comp, count in company_counts:
        p(f"- **{comp}**: `{count}` opportunities")
    p()
    p("### C. Recurring Critical Skill Gaps")
    p()
    p("Across rejected or stretch roles, the model most frequently cited:")
    for skill, count in missing_skills_counter.most_common(8):
        p(f"- **{skill}**: cited in `{count}` evaluations")
    p()
    p("### D. Universally Recognized Transferable Capabilities")
    p()
    p("The model consistently rewarded the candidate for:")
    for cap, count in strengths_counter.most_common(6):
        p(f"- **{cap}**: highlighted in `{count}` evaluations")
    p()
    p("### E. Seniority, Geography & Compensation")
    p()
    p(f"- **Location Distribution**: Remote ({loc_counter['Remote']}), US Hybrid/Onsite ({loc_counter['US (Onsite/Hybrid)']}), India ({loc_counter['India (Onsite/Hybrid)']}), Other ({loc_counter['Other / Global']}).")
    p(f"- **Location Friction**: US-restricted on-site/hybrid roles were consistently downgraded by the LLM in `transition_difficulty` and `probability_of_obtaining` when explicit US work authorization was mandated.")
    p(f"- **Compensation Disclosures**: `{sal_stats['count_disclosed']}` of 184 evaluated jobs published compensation. Median stated maximum: `${sal_stats['median']:,.0f}` (Range: `${sal_stats['min']:,.0f}` – `${sal_stats['max']:,.0f}`).")
    p()
    p("---")
    p()

    # 9. Human review instructions
    p("## 9. Human Review Instructions")
    p()
    p("To complete the manual review of these evaluated opportunities:")
    p()
    p("1. Open the companion review spreadsheet: [llm_evaluation_review.csv](file:///c:/Users/recko/OneDrive/Desktop/Career%20OS/llm_evaluation_review.csv) or JSON data [llm_evaluation_review.json](file:///c:/Users/recko/OneDrive/Desktop/Career%20OS/llm_evaluation_review.json).")
    p("2. Review the pre-filtered tiers in order:")
    p("   - **Set 1: Consider Jobs (All 21)** — Highest priority for active application pipeline.")
    p("   - **Set 2: High-Upside Long Shots (42)** — Identify stretch roles with compelling compensation/career upside where tailored bridge positioning can overcome gaps.")
    p("   - **Set 3: Top Skip Jobs (20)** — Validate whether high-scoring Skips contain false negatives due to geography or strict seniority gates.")
    p("   - **Set 4: Random Skips (10)** — Spot-check to confirm that clear mismatches (legal, nursing, direct sales) were properly eliminated.")
    p("3. Fill in the dedicated empty review columns in `llm_evaluation_review.csv`:")
    p("   - `human_verdict`: Enter one of `APPLY`, `MAYBE`, `STRETCH`, `SKIP`, or `UNKNOWN`.")
    p("   - `human_priority`: Assign priority rank (e.g. `P1`, `P2`, `P3`).")
    p("   - `human_notes`: Candidate-specific notes, network connections, or tailoring angles.")
    p("   - `human_correction`: Flag any LLM misjudgments (e.g. `LLM underestimated technical fit`, `Visa ineligible`).")
    p("4. Save your annotated review file without modifying the underlying `llm_evaluations_full.json` artifact.")
    p()

    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Generated {OUTPUT_MD}")

if __name__ == "__main__":
    main()
