"""
scripts/inspect_run002_metrics.py — Extract and display complete Run 001 -> Run 002 longitudinal comparison.
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.db.repository import CareerOSRepository
from career_os.db.migrate_json_to_sqlite import EXPECTED_RESULTS_SHA256, EXPECTED_EVALS_SHA256


def inspect():
    conn = sqlite3.connect("career_os.db")
    conn.row_factory = sqlite3.Row

    print("=" * 70)
    print("CAREER OS — RUN 001 -> RUN 002 LONGITUDINAL PRODUCTION REPORT")
    print("=" * 70)

    # 1. Discovery Runs Table
    print("\n--- 1. DISCOVERY RUNS IN DATABASE ---")
    runs = conn.execute("SELECT * FROM discovery_runs ORDER BY run_number ASC;").fetchall()
    for r in runs:
        print(f"Run {r['run_number']:03d} ({r['id']}):")
        print(f"  Status                  : {r['status']}")
        print(f"  Started                 : {r['started_at']}")
        print(f"  Completed               : {r['completed_at']}")
        print(f"  Total Raw Records       : {r['total_raw_records']}")
        print(f"  Total Unique Deduped    : {r['total_unique_opportunities']}")
        print(f"  New Opportunities       : {r['new_opportunities']}")
        print(f"  Previously Seen         : {r['previously_seen_opportunities']}")
        print(f"  Already Applied         : {r['already_applied_opportunities']}")
        print(f"  Already Reviewed        : {r['already_reviewed_opportunities']}")
        print(f"  Evaluations Required    : {r['evaluations_required']}")
        print(f"  Evaluations Reused      : {r['evaluations_reused']}")
        print(f"  LLM Calls Avoided       : {r['llm_calls_avoided']}")
        print()

    # 2. Cumulative Opportunity Store
    total_opps = conn.execute("SELECT COUNT(*) FROM opportunities;").fetchone()[0]
    print("--- 2. CUMULATIVE OPPORTUNITY STORE ---")
    print(f"Total Unique Opportunities in Database: {total_opps}")

    # 3. Longitudinal Delta Breakdown
    opps_run1_only = conn.execute("SELECT COUNT(*) FROM opportunities WHERE first_seen_run_id = 'run_0001' AND last_seen_run_id = 'run_0001';").fetchone()[0]
    opps_both_runs = conn.execute("SELECT COUNT(*) FROM opportunities WHERE first_seen_run_id = 'run_0001' AND last_seen_run_id = 'run_0002';").fetchone()[0]
    opps_run2_new = conn.execute("SELECT COUNT(*) FROM opportunities WHERE first_seen_run_id = 'run_0002';").fetchone()[0]

    print("\n--- 3. LONGITUDINAL PRESENCE & CHURN ---")
    print(f"Run 001 Total Baseline Opportunities          : 129")
    print(f"  |-- Disappeared in Run 002 (Only in Run 001) : {opps_run1_only} ({opps_run1_only / 129 * 100:.1f}% churn)")
    print(f"  \\-- Recurring in Run 002 (Active in both)    : {opps_both_runs} ({opps_both_runs / 129 * 100:.1f}% retention)")
    print(f"Run 002 Newly Discovered Opportunities         : {opps_run2_new}")
    print(f"Run 002 Total Discovered (Recurring + New)     : {opps_both_runs + opps_run2_new}")

    # 4. Applied Opportunities
    applied_all = conn.execute("SELECT id, title, company, current_application_status, appearance_count, last_seen_run_id FROM opportunities WHERE current_application_status = 'APPLIED';").fetchall()
    applied_seen_run2 = [a for a in applied_all if a['last_seen_run_id'] == 'run_0002']

    print("\n--- 4. APPLICATION MEMORY PRESERVATION ---")
    print(f"Total APPLIED Opportunities in Database       : {len(applied_all)}")
    print(f"APPLIED Opportunities Rediscovered in Run 002 : {len(applied_seen_run2)}")
    for a in applied_seen_run2:
        print(f"  • [{a['id']}] {a['title']} @ {a['company']}")
        print(f"    Status: {a['current_application_status']} | Lifetime Appearances: {a['appearance_count']} | Last Seen: {a['last_seen_run_id']}")

    # 5. Reuse & Conservation Invariants
    run2 = runs[-1]
    raw_r2 = run2['total_raw_records']
    uniq_r2 = run2['total_unique_opportunities']
    prov_m = json.loads(run2['provider_metrics_json'] or "{}")

    intra_dupes = sum(p.get('duplicates', 0) for p in prov_m.values())
    cross_dupes = sum(p.get('unique', 0) for p in prov_m.values()) - uniq_r2
    total_dupes = intra_dupes + cross_dupes

    print("\n--- 5. CONSERVATION & EFFICIENCY INVARIANTS ---")
    print(f"Raw ({raw_r2}) - Duplicates ({total_dupes}) == Unique ({uniq_r2}) : {raw_r2 - total_dupes == uniq_r2}")
    print(f"LLM Calls Avoided ({run2['llm_calls_avoided']}) == Evaluations Reused ({run2['evaluations_reused']}) : {run2['llm_calls_avoided'] == run2['evaluations_reused']}")

    # 6. Immutable Hashes
    def sha256(p):
        with open(p, "rb") as f: return hashlib.sha256(f.read()).hexdigest()

    h1 = sha256("india_discovery_results.json")
    h2 = sha256("india_discovery_llm_evaluations.json")

    print("\n--- 6. IMMUTABLE HISTORICAL DATASET VERIFICATION ---")
    print(f"india_discovery_results.json SHA-256 Match       : {h1 == EXPECTED_RESULTS_SHA256} ({h1})")
    print(f"india_discovery_llm_evaluations.json SHA-256 Match : {h2 == EXPECTED_EVALS_SHA256} ({h2})")
    print("=" * 70)


if __name__ == "__main__":
    inspect()
