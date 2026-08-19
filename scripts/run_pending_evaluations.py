"""
scripts/run_pending_evaluations.py — Execute LLM evaluations for all PENDING opportunities in Career OS.
Transactional, resumable, rate-limited execution.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from career_os.discovery.evaluator_runner import EvaluationRunner


def main():
    print("=" * 70)
    print("CAREER OS — RUN 002 PENDING EVALUATION EXECUTION")
    print("=" * 70)

    db_file = sys.argv[1] if len(sys.argv) > 1 else "career_os.db"
    runner = EvaluationRunner(
        db_path=db_file,
        cv_path="Tushar_Chaand_CV.docx",
        inter_call_delay=1.0,
    )

    metrics = runner.run()

    print("\n" + "=" * 70)
    print("FINAL EXECUTION ACCOUNTING REPORT")
    print("-" * 70)
    for k, v in metrics.items():
        print(f"  {k:<32}: {v}")
    print("=" * 70)

    if metrics.get("remaining_pending", 0) == 0:
        print("\nSUCCESS: All pending opportunities have received an evaluation state.")
    else:
        print(f"\nWARNING: {metrics.get('remaining_pending')} opportunities remain pending.")


if __name__ == "__main__":
    main()
