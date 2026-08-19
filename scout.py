#!/usr/bin/env python3
"""
scout.py — Tier 1 Job Spy Validation
Runs 5 high-precision queries against Indeed + LinkedIn, reports stats.
"""

import json
import sys
from jobspy import scrape_jobs

# Tier 1 queries from search strategy
TIER1_QUERIES = [
    "Product Analyst fintech",
    "Associate Product Manager payments",
    "Product Manager KYC compliance",
    "Product Owner fintech",
    "Digital Product Manager enterprise platform",
]

# Sites to query (per strategy: Indeed + LinkedIn first)
TIER1_SITES = ["indeed", "linkedin"]

# Output files
JOBS_OUTPUT = "tier1_jobs.json"
REPORT_OUTPUT = "tier1_search_report.md"


def _safe_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        return "" if val != val else str(val)  # NaN check
    return str(val)


def normalize_job(raw: dict) -> dict:
    """Map JobSpy row to consistent schema. Uses raw['site'] for actual source."""
    return {
        "title": _safe_str(raw.get("title", "")),
        "company": _safe_str(raw.get("company", "")),
        "location": _safe_str(raw.get("location", "")),
        "description": _safe_str(raw.get("description", "")),
        "job_url": _safe_str(raw.get("job_url", "")),
        "salary_min": raw.get("min_amount"),
        "salary_max": raw.get("max_amount"),
        "salary_interval": _safe_str(raw.get("interval", "")),
        "is_remote": raw.get("is_remote", False) or False,
        "job_type": _safe_str(raw.get("job_type", "")),
        "site": _safe_str(raw.get("site", "")),
        "date_posted": _safe_str(raw.get("date_posted", "")),
    }


def dedupe_jobs(jobs: list) -> list:
    """Deduplicate by title + company + location hash. Merge sources."""
    seen = {}
    for j in jobs:
        key = (j["title"].strip().lower(), j["company"].strip().lower(), j["location"].strip().lower())
        if key not in seen:
            # Initialize sources array
            j["sources"] = [j.get("site", "")]
            seen[key] = j
        else:
            # Merge source
            src = j.get("site", "")
            if src and src not in seen[key]["sources"]:
                seen[key]["sources"].append(src)
            # Keep earliest date_posted
            if j.get("date_posted") and (not seen[key].get("date_posted") or j["date_posted"] < seen[key]["date_posted"]):
                seen[key]["date_posted"] = j["date_posted"]
    return list(seen.values())


def apply_deterministic_filters(jobs: list) -> tuple:
    """
    Apply Tier 1 deterministic filters.
    Returns (kept, rejected_counts)
    """
    kept = []
    rejected = {
        "salary_floor": 0,
        "excluded_keywords": 0,
        "freshness": 0,
    }

    EXCLUDE_KEYWORDS = [
        "engineer", "developer", "embedded", "devops", "cyber",
        "aerospace", "firmware", "hardware", "sales", "intern",
        "junior", "entry", "recruiter", "hr ", "human resources",
        "business analyst", "project manager", "scrum master",
        "data engineer", "ml engineer", "machine learning engineer",
        "software engineer", "backend", "frontend", "fullstack",
        "full stack", "compiler", "rtos", "kernel", "driver",
        "qa ", "quality assurance", "test engineer", "sdet",
        "devsecops", "sre ", "site reliability", "infrastructure",
        "platform engineer", "cloud engineer", "network engineer",
    ]

    INCLUDE_KEYWORDS = [
        "product", "payments", "k y c", "kyc", "compliance", "risk",
        "fintech", "case", "platform", "analyst", "owner",
        "digital product", "associate product", "product manager",
        "product owner", "product analyst",
    ]

    for j in jobs:
        title = j.get("title", "").lower()
        desc = j.get("description", "").lower()
        haystack = f"{title} {desc}"
        site = j.get("site", "")
        salary_min = j.get("salary_min")
        salary_max = j.get("salary_max")
        date_posted = j.get("date_posted", "")

        # Exclude keywords (hard filter on title)
        excluded = False
        for kw in EXCLUDE_KEYWORDS:
            if kw in title:
                rejected["excluded_keywords"] += 1
                excluded = True
                break
        if excluded:
            continue

        # Must have at least one include keyword in title OR description
        has_include = False
        for kw in INCLUDE_KEYWORDS:
            if kw in haystack:
                has_include = True
                break
        if not has_include:
            rejected["excluded_keywords"] += 1
            continue

        # Salary floor by market (soft - only reject if clearly below)
        # India: ~15L INR ≈ $18K USD; US: $80K
        # Only filter if we have salary data AND it's clearly wrong market
        if salary_min:
            if salary_min < 18000 and "indeed" in site.lower():  # Likely hourly or wrong currency
                rejected["salary_floor"] += 1
                continue

        # Freshness - skip if older than 30 days (approximate)
        # JobSpy returns date_posted as string, skip if clearly old
        # We'll rely on hours_old=168 (7 days) in query instead

        kept.append(j)

    return kept, rejected


def run_query(query: str, site: str, results_wanted: int = 25) -> tuple:
    """
    Run a single query against a single site.
    Returns (jobs_list, error_message_or_None)
    """
    try:
        df = scrape_jobs(
            site_name=[site],
            search_term=query,
            location=None,  # No location filter for remote-friendly
            results_wanted=results_wanted,
            hours_old=168,  # 7 days
            country_indeed="USA",
        )
        raw = df.to_dict("records")
        return raw, None
    except Exception as e:
        return [], str(e)


def main():
    print("=" * 60)
    print("TIER 1 JOB SPY VALIDATION RUN")
    print("=" * 60)

    all_raw_jobs = []
    report_lines = []
    report_lines.append("# Tier 1 Search Report\n")
    report_lines.append(f"**Queries:** {len(TIER1_QUERIES)}")
    report_lines.append(f"**Sites:** {TIER1_SITES}")
    report_lines.append("")

    query_stats = []

    for query in TIER1_QUERIES:
        print(f"\n==> Query: '{query}'")
        report_lines.append(f"## Query: `{query}`\n")

        query_raw = 0
        query_normalized = 0
        query_deduped = 0
        query_filtered = 0
        query_final = 0
        site_failures = []

        for site in TIER1_SITES:
            print(f"  Site: {site}...", end=" ", flush=True)
            raw, err = run_query(query, site)
            if err:
                print(f"FAILED: {err}")
                site_failures.append({"site": site, "error": err})
                report_lines.append(f"- **{site}**: FAILED — {err}")
                continue

            raw_count = len(raw)
            query_raw += raw_count
            print(f"{raw_count} raw", end=" ")

            normalized = [normalize_job(j) for j in raw]
            query_normalized += len(normalized)

            all_raw_jobs.extend(normalized)

            report_lines.append(f"- **{site}**: {raw_count} raw → {len(normalized)} normalized")

        # Dedupe across sites for this query
        deduped = dedupe_jobs(all_raw_jobs[-query_normalized:]) if query_normalized > 0 else []
        query_deduped = len(deduped)

        # Apply deterministic filters
        kept, rejected = apply_deterministic_filters(deduped)
        query_filtered = len(kept)
        query_final = query_filtered

        print(f"| deduped: {query_deduped} | kept: {query_final}")

        report_lines.append(f"- **After dedupe (cross-site)**: {query_deduped}")
        report_lines.append(f"- **After deterministic filters**: {query_final}")
        if rejected:
            report_lines.append(f"- **Rejected**: salary_floor={rejected['salary_floor']}, excluded_keywords={rejected['excluded_keywords']}, freshness={rejected['freshness']}")
        if site_failures:
            report_lines.append(f"- **Site failures**: {site_failures}")

        query_stats.append({
            "query": query,
            "raw": query_raw,
            "normalized": query_normalized,
            "deduped": query_deduped,
            "kept": query_final,
            "rejected": rejected,
            "site_failures": site_failures,
        })

    # Final global dedupe across all queries
    print("\n" + "=" * 60)
    print("GLOBAL DEDUPLICATION ACROSS ALL QUERIES")
    print("=" * 60)

    final_deduped = dedupe_jobs(all_raw_jobs)
    print(f"Total normalized: {len(all_raw_jobs)}")
    print(f"After global dedupe: {len(final_deduped)}")

    final_kept, final_rejected = apply_deterministic_filters(final_deduped)
    print(f"After global filters: {len(final_kept)}")

    report_lines.append("\n## Global Summary\n")
    report_lines.append(f"- **Total raw jobs (all queries, all sites)**: {sum(s['raw'] for s in query_stats)}")
    report_lines.append(f"- **Total normalized**: {len(all_raw_jobs)}")
    report_lines.append(f"- **After global dedupe**: {len(final_deduped)}")
    report_lines.append(f"- **After global deterministic filters**: {len(final_kept)}")

    # Save tier1_jobs.json
    with open(JOBS_OUTPUT, "w") as f:
        json.dump(final_kept, f, indent=2, default=str)
    print(f"\nSaved {len(final_kept)} jobs to {JOBS_OUTPUT}")

    # Save report
    report_lines.append("\n## Retained Jobs (Sample)\n")
    for j in final_kept[:20]:
        sources = ", ".join(j.get("sources", [j.get("site", "")]))
        report_lines.append(f"- **{j['title']}** — {j['company']} — {j['location']} — {j['site']} ({sources})")

    report_lines.append("\n---\n*End of Tier 1 report*")

    with open(REPORT_OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"Saved report to {REPORT_OUTPUT}")

    # Print summary
    print("\n" + "=" * 60)
    print("TIER 1 SUMMARY")
    print("=" * 60)
    for qs in query_stats:
        print(f"  {qs['query'][:40]:40s} | raw={qs['raw']:3d} | kept={qs['kept']:3d}")
    print(f"\n  TOTAL KEPT: {len(final_kept)}")


if __name__ == "__main__":
    main()