"""
eval/run_eval_batch.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Offline batch eval runner — Week 5 carry-over pattern.

In Week 5 this script pulled QA pairs from the RAG pipeline DB and
re-scored them with the RAGAS metrics. Here it pulls feedback rows
from the interview coach DB and re-scores them with the 4 interview
eval metrics (rubric_coverage, actionability, consistency, PII).

Usage:
    python eval/run_eval_batch.py                  # all unscored feedback
    python eval/run_eval_batch.py --limit 50       # last 50 feedback rows
    python eval/run_eval_batch.py --rescore        # re-score all (overwrite)
    python eval/run_eval_batch.py --report         # print summary table only

Output:
    eval/results/eval_batch_<timestamp>.json       # raw scores
    console: pass/fail summary table
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Allow import from app/ without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

import psycopg2
import psycopg2.extras
from eval_layer import (
    score_rubric_coverage,
    score_actionability,
    score_consistency,
    redact_pii,
    RUBRIC_COVERAGE_THRESHOLD,
    ACTIONABILITY_THRESHOLD,
    CONSISTENCY_DELTA_MAX,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"


def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "wynisco"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def fetch_feedback_rows(limit: int, rescore: bool) -> list[dict]:
    """
    Pull feedback rows from DB joined with session + rubric.
    If rescore=False, skip feedback_ids that already have eval_scores rows.
    """
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        already_scored_clause = "" if rescore else "AND e.id IS NULL"
        cur.execute(
            f"""
            SELECT
                f.id             AS feedback_id,
                f.session_id,
                f.clarity,
                f.depth,
                f.star_format,
                f.red_flags,
                f.suggestions,
                f.raw_response,
                s.question_text,
                s.answer_text,
                r.dimensions     AS rubric_dimensions
            FROM feedback f
            JOIN sessions s ON s.id = f.session_id
            JOIN rubrics  r ON r.id = s.rubric_id
            LEFT JOIN eval_scores e ON e.feedback_id = f.id
            WHERE 1=1 {already_scored_clause}
            ORDER BY f.created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def run_batch(rows: list[dict]) -> list[dict]:
    """Score each feedback row with all 4 Week 5 eval metrics."""
    results = []
    for row in rows:
        fid = row["feedback_id"]

        # Parse JSONB fields (psycopg2 returns them as dicts/lists already)
        raw = row["raw_response"] or {}
        feedback = {
            "clarity":     row["clarity"],
            "depth":       row["depth"],
            "star_format": row["star_format"],
            "summary":     raw.get("summary", ""),
            "suggestions": row["suggestions"] if isinstance(row["suggestions"], list)
                           else json.loads(row["suggestions"] or "[]"),
            "red_flags":   row["red_flags"]   if isinstance(row["red_flags"],   list)
                           else json.loads(row["red_flags"]   or "[]"),
        }
        dims = row["rubric_dimensions"] if isinstance(row["rubric_dimensions"], list) \
               else json.loads(row["rubric_dimensions"] or "[]")

        # --- Week 5 metric 1: Faithfulness → Rubric Coverage ---
        rubric_coverage = score_rubric_coverage(feedback, dims)

        # --- Week 5 metric 2: Answer Relevance → Actionability ---
        actionability = score_actionability(feedback)

        # --- Week 5 metric 3: Context Precision → Consistency ---
        consistency_delta = score_consistency(
            session_id=str(row["session_id"]),
            question_text=row["question_text"],
            current_clarity=row["clarity"],
            current_depth=row["depth"],
            current_star=row["star_format"],
        )

        # --- Week 5 metric 4: PII Guardrail (reused directly) ---
        _, pii_detected = redact_pii(row.get("answer_text", ""))

        eval_passed = (
            rubric_coverage >= RUBRIC_COVERAGE_THRESHOLD
            and actionability >= ACTIONABILITY_THRESHOLD
            and (consistency_delta is None or consistency_delta <= CONSISTENCY_DELTA_MAX)
        )

        result = {
            "feedback_id":       fid,
            "session_id":        str(row["session_id"]),
            "rubric_coverage":   rubric_coverage,
            "actionability":     actionability,
            "consistency_delta": consistency_delta,
            "pii_detected":      pii_detected,
            "eval_passed":       eval_passed,
        }
        results.append(result)
        logger.info(
            f"[{fid}] coverage={rubric_coverage:.2f} action={actionability:.2f} "
            f"consist={consistency_delta} pii={pii_detected} "
            f"{'PASS' if eval_passed else 'FAIL'}"
        )
    return results


def save_results(results: list[dict]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_batch_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved → {out_path}")
    return out_path


def print_summary(results: list[dict]):
    if not results:
        print("No results to summarise.")
        return

    total   = len(results)
    passed  = sum(1 for r in results if r["eval_passed"])
    failed  = total - passed

    avg_cov    = sum(r["rubric_coverage"] for r in results) / total
    avg_act    = sum(r["actionability"]   for r in results) / total
    deltas     = [r["consistency_delta"] for r in results if r["consistency_delta"] is not None]
    avg_delta  = sum(deltas) / len(deltas) if deltas else None
    pii_count  = sum(1 for r in results if r["pii_detected"])

    print("\n" + "=" * 60)
    print("  WYNISCO EVAL BATCH REPORT  (Week 5 metrics → Week 6)")
    print("=" * 60)
    print(f"  Sessions evaluated : {total}")
    print(f"  Passed             : {passed} ({passed/total:.0%})")
    print(f"  Failed             : {failed} ({failed/total:.0%})")
    print("-" * 60)
    print(f"  Avg Rubric Coverage  (≥{RUBRIC_COVERAGE_THRESHOLD:.0%}) : {avg_cov:.1%}")
    print(f"  Avg Actionability    (≥{ACTIONABILITY_THRESHOLD:.0%}) : {avg_act:.1%}")
    if avg_delta is not None:
        print(f"  Avg Consistency Δ   (≤{CONSISTENCY_DELTA_MAX})   : {avg_delta:.3f}")
    else:
        print(f"  Consistency Δ                     : n/a (first sessions)")
    print(f"  PII detections                    : {pii_count}/{total}")
    print("=" * 60 + "\n")

    # Per-metric pass/fail breakdown
    print(f"  {'Metric':<25} {'Threshold':<12} {'Avg Score':<12} {'Status'}")
    print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*8}")
    print(f"  {'Rubric Coverage':<25} {'≥70%':<12} {avg_cov:.1%:<12} "
          f"{'✅ PASS' if avg_cov >= RUBRIC_COVERAGE_THRESHOLD else '❌ FAIL'}")
    print(f"  {'Actionability':<25} {'≥70%':<12} {avg_act:.1%:<12} "
          f"{'✅ PASS' if avg_act >= ACTIONABILITY_THRESHOLD else '❌ FAIL'}")
    if avg_delta is not None:
        print(f"  {'Consistency Δ':<25} {'≤0.5':<12} {avg_delta:<12.3f} "
              f"{'✅ PASS' if avg_delta <= CONSISTENCY_DELTA_MAX else '❌ FAIL'}")
    print(f"  {'PII Guardrail':<25} {'0 leaks':<12} {pii_count} detected  "
          f"{'✅ PASS' if pii_count == 0 else '⚠️  REVIEW'}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Wynisco offline eval batch runner")
    parser.add_argument("--limit",   type=int, default=200, help="Max feedback rows to score")
    parser.add_argument("--rescore", action="store_true",   help="Re-score already-evaluated rows")
    parser.add_argument("--report",  action="store_true",   help="Print summary of latest results file only")
    args = parser.parse_args()

    if args.report:
        # Find latest results file and print its summary
        files = sorted(RESULTS_DIR.glob("eval_batch_*.json"))
        if not files:
            print("No result files found. Run without --report first.")
            sys.exit(1)
        latest = files[-1]
        with open(latest) as f:
            results = json.load(f)
        print(f"Loaded: {latest}")
        print_summary(results)
        return

    logger.info(f"Fetching up to {args.limit} feedback rows (rescore={args.rescore})…")
    rows = fetch_feedback_rows(limit=args.limit, rescore=args.rescore)

    if not rows:
        print("No feedback rows to evaluate. Submit some sessions first.")
        sys.exit(0)

    logger.info(f"Scoring {len(rows)} rows…")
    results = run_batch(rows)
    save_results(results)
    print_summary(results)


if __name__ == "__main__":
    main()
