#!/usr/bin/env python3
"""
Run Scoring v2 evaluation on Tier 1 jobs.
"""

import json
import sys
import os

# Add career_os to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from career_os.scoring import evaluate_jobs, summarize_evaluation, filter_by_category, get_top_n


def load_jobs(path: str):
    """Load jobs from tier1_jobs.json and add job_id."""
    with open(path, "r", encoding="utf-8") as f:
        jobs = json.load(f)
    
    for i, job in enumerate(jobs):
        if "job_id" not in job:
            job["job_id"] = f"job_{i:04d}"
    return jobs


def main():
    print("=" * 60)
    print("SCORING v2 EVALUATION — Tier 1 Jobs (196)")
    print("=" * 60)
    
    # Load jobs
    jobs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tier1_jobs.json")
    jobs = load_jobs(jobs_path)
    print(f"Loaded {len(jobs)} jobs from {jobs_path}")
    
    # Evaluate
    print("\nEvaluating jobs...")
    evaluations = evaluate_jobs(jobs)
    
    # Summary
    summary = summarize_evaluation(evaluations)
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total evaluated: {summary['total_evaluated']}")
    print(f"Categories: A={summary['category_counts']['A']}, B={summary['category_counts']['B']}, C={summary['category_counts']['C']}, D={summary['category_counts']['D']}")
    print(f"Average score: {summary['average_score']}")
    print(f"Median score: {summary['median_score']}")
    print(f"Product roles: {summary['product_roles']}")
    print(f"Non-product roles: {summary['non_product_roles']}")
    print(f"Eligible (passed gates): {summary['eligible_jobs']}")
    
    print("\nTop Gate Failures:")
    for failure, count in summary['top_gate_failures']:
        print(f"  {count:3d} — {failure}")
    
    # Category A jobs
    a_jobs = filter_by_category(evaluations, "A")
    print(f"\n{'='*60}")
    print(f"CATEGORY A — STRONG APPLY ({len(a_jobs)})")
    print(f"{'='*60}")
    for i, job in enumerate(a_jobs):
        print(f"  {i+1}. [{job['overall_score']}] {job['title'][:50]} | {job['company'][:25]} | {job['location'][:20]}")
        print(f"      Breakdown: {job['breakdown']}")
        print(f"      Why: {job['recommendation']}")
    
    # Category B jobs (top 20)
    b_jobs = filter_by_category(evaluations, "B")
    print(f"\n{'='*60}")
    print(f"CATEGORY B — WORTH CONSIDERING (showing top 20 of {len(b_jobs)})")
    print(f"{'='*60}")
    for i, job in enumerate(b_jobs[:20]):
        print(f"  {i+1}. [{job['overall_score']}] {job['title'][:50]} | {job['company'][:25]} | {job['location'][:20]}")
        print(f"      Domain: {job['domain_classification']} | Breakdown: {job['breakdown']}")
    
    # Top 10 overall
    top_10 = get_top_n(evaluations, 10)
    print(f"\n{'='*60}")
    print("TOP 10 OVERALL")
    print(f"{'='*60}")
    for i, job in enumerate(top_10):
        print(f"  {i+1}. [{job['overall_score']}][{job['category']}] {job['title'][:45]} | {job['company'][:25]} | {job['location'][:20]} | {job['domain_classification']}")
    
    # Save full evaluation
    output = {
        "evaluations": evaluations,
        "summary": summary
    }
    with open("scoring_v2_evaluation.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nFull evaluation saved to scoring_v2_evaluation.json")


if __name__ == "__main__":
    import json
    main()