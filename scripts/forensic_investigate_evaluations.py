"""
scripts/forensic_investigate_evaluations.py — Read-only forensic investigation tool.
Audits database records, JSON fixtures, API responses, and frontend mappings.
"""

import json
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def forensic_audit():
    conn = sqlite3.connect("career_os.db")
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print("CAREER OS — FORENSIC EVALUATION AUDIT")
    print("=" * 80)

    # 1. Row counts
    n_opps = conn.execute("SELECT COUNT(*) FROM opportunities;").fetchone()[0]
    n_evals = conn.execute("SELECT COUNT(*) FROM evaluations;").fetchone()[0]
    n_reviews = conn.execute("SELECT COUNT(*) FROM human_reviews;").fetchone()[0]
    n_runs = conn.execute("SELECT COUNT(*) FROM discovery_runs;").fetchone()[0]

    print(f"Total Opportunities in SQLite : {n_opps}")
    print(f"Total Evaluations in SQLite   : {n_evals}")
    print(f"Total Human Reviews in SQLite : {n_reviews}")
    print(f"Total Discovery Runs in SQLite: {n_runs}")

    # 2. Opportunities with and without evaluations
    opps_with_eval = conn.execute("SELECT COUNT(DISTINCT opportunity_id) FROM evaluations;").fetchone()[0]
    print(f"Opportunities WITH Evaluation in DB   : {opps_with_eval}")
    print(f"Opportunities WITHOUT Evaluation in DB: {n_opps - opps_with_eval}")

    # 3. Check sample records in evaluations table
    print("\n--- SAMPLE EVALUATION RECORDS FROM SQLITE ---")
    samples = ["disc_0001", "disc_0015", "disc_0040", "disc_0057", "disc_0092", "disc_0130", "disc_0135"]
    for sid in samples:
        row = conn.execute("SELECT * FROM evaluations WHERE opportunity_id = ?;", (sid,)).fetchone()
        if row:
            print(f"Opportunity {sid} (Evaluation ID: {row['id']}):")
            print(f"  recommendation : {row['recommendation']}")
            print(f"  score          : {row['score']}")
            print(f"  fit_dimensions : {row['fit_dimensions_json']}")
            print(f"  strengths      : {row['strengths_json']}")
            print(f"  gaps           : {row['gaps_json']}")
            print(f"  reasoning[:80] : {str(row['reasoning'])[:80]}...")
            print(f"  is_reused      : {row['is_reused']} (type: {row['reuse_type']})")
        else:
            print(f"Opportunity {sid}: [NO EVALUATION ROW IN SQLITE]")

    # 4. Check historical JSON vs SQLite for disc_0001, disc_0040, disc_0057
    print("\n--- HISTORICAL JSON vs SQLITE COMPARISON ---")
    with open("india_discovery_llm_evaluations.json", "r", encoding="utf-8") as f:
        json_evals_data = json.load(f)
    json_eval_map = {}
    for ev in json_evals_data.get("evaluations", []):
        jid = ev.get("discovery_id") or ev.get("job_id")
        if jid:
            json_eval_map[jid] = ev

    for sid in ["disc_0001", "disc_0040", "disc_0057", "disc_0092"]:
        jev = json_eval_map.get(sid, {})
        j_llm = jev.get("llm_evaluation", {}) or {}
        db_row = conn.execute("SELECT * FROM evaluations WHERE opportunity_id = ?;", (sid,)).fetchone()

        print(f"\nComparing {sid}:")
        print(f"  JSON recommendation    : {j_llm.get('recommendation')}")
        print(f"  JSON score             : {j_llm.get('score')}")
        print(f"  JSON fit_dimensions    : {j_llm.get('fit_dimensions')}")
        print(f"  JSON strengths         : {j_llm.get('strengths')}")
        print(f"  JSON gaps              : {j_llm.get('gaps')}")
        print(f"  JSON reasoning[:60]    : {str(j_llm.get('reasoning'))[:60]}...")

        if db_row:
            print(f"  SQLite recommendation  : {db_row['recommendation']}")
            print(f"  SQLite score           : {db_row['score']}")
            print(f"  SQLite fit_dimensions  : {db_row['fit_dimensions_json']}")
            print(f"  SQLite strengths       : {db_row['strengths_json']}")
            print(f"  SQLite gaps            : {db_row['gaps_json']}")
            print(f"  SQLite reasoning[:60]  : {str(db_row['reasoning'])[:60]}...")

    # 5. Check counts of populated structured fields in evaluations table
    print("\n--- STRUCTURED FIELD POPULATION AUDIT IN SQLITE ---")
    all_evals = conn.execute("SELECT * FROM evaluations;").fetchall()
    with_score = 0
    with_fit_dims = 0
    with_strengths = 0
    with_gaps = 0
    with_reasoning = 0

    for ev in all_evals:
        if ev["score"] is not None:
            with_score += 1
        dims = json.loads(ev["fit_dimensions_json"] or "{}")
        if dims and any(v is not None for v in dims.values()):
            with_fit_dims += 1
        st = json.loads(ev["strengths_json"] or "[]")
        if st and len(st) > 0:
            with_strengths += 1
        gp = json.loads(ev["gaps_json"] or "[]")
        if gp and len(gp) > 0:
            with_gaps += 1
        if ev["reasoning"] and len(str(ev["reasoning"]).strip()) > 0:
            with_reasoning += 1

    print(f"Total Evaluations                      : {len(all_evals)}")
    print(f"Evaluations with score populated       : {with_score}")
    print(f"Evaluations with fit_dimensions pop.   : {with_fit_dims}")
    print(f"Evaluations with strengths > 0 items   : {with_strengths}")
    print(f"Evaluations with gaps > 0 items        : {with_gaps}")
    print(f"Evaluations with reasoning populated   : {with_reasoning}")


if __name__ == "__main__":
    forensic_audit()
