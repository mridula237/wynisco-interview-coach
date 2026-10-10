# eval/

Offline evaluation scripts for the Wynisco AI Interview Coach.  
These mirror the Week 5 RAG eval pipeline, adapted to the interview coaching domain.

---

## Files

| File | Purpose |
|------|---------|
| `metrics.py` | Single source of truth — Week 5 → Week 6 metric definitions and thresholds |
| `run_eval_batch.py` | Pulls feedback from DB, re-scores with all 4 eval metrics, saves JSON results |
| `results/` | Auto-created by `run_eval_batch.py` — stores `eval_batch_<timestamp>.json` |

---

## Week 5 → Week 6 Metric Mapping

| Week 5 Metric | Week 6 Analog | Threshold | Function |
|---------------|---------------|-----------|----------|
| Faithfulness | Rubric Coverage | ≥ 70% | `score_rubric_coverage()` |
| Answer Relevance | Actionability | ≥ 70% | `score_actionability()` |
| Context Precision | Consistency Δ | ≤ 0.5 | `score_consistency()` |
| PII Guardrail | PII Guardrail | 0 leaks | `redact_pii()` |

All scoring logic lives in `app/eval_layer.py`.  
This folder runs that logic **offline** (batch) against historical DB records.

---

## Usage

```bash
# From project root, with .env loaded:
source .env  # or: export $(cat .env | xargs)

# Score all unscored feedback rows
python eval/run_eval_batch.py

# Score last 50 rows
python eval/run_eval_batch.py --limit 50

# Re-score everything (overwrite existing eval_scores)
python eval/run_eval_batch.py --rescore

# Print summary of the latest results file (no DB needed)
python eval/run_eval_batch.py --report

# Print the metric mapping table
python eval/metrics.py
```

Or via `run.sh`:
```bash
./run.sh test   # runs pytest unit tests (not this batch runner)
```

---

## Output

`results/eval_batch_<timestamp>.json` — list of scored rows:

```json
[
  {
    "feedback_id": 42,
    "session_id": "uuid...",
    "rubric_coverage": 0.75,
    "actionability": 0.80,
    "consistency_delta": null,
    "pii_detected": false,
    "eval_passed": true
  }
]
```

Console summary:

```
============================================================
  WYNISCO EVAL BATCH REPORT  (Week 5 metrics → Week 6)
============================================================
  Sessions evaluated : 20
  Passed             : 17 (85%)
  Failed             : 3 (15%)
------------------------------------------------------------
  Avg Rubric Coverage  (≥70%) : 83.0%
  Avg Actionability    (≥70%) : 78.0%
  Avg Consistency Δ   (≤0.5) : 0.21
  PII detections              : 0/20
============================================================
```
