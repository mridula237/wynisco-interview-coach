"""
eval/metrics.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Week 5 → Week 6 eval metric definitions and thresholds.
This file is the single source of truth for how each metric maps.
Imported by run_eval_batch.py and referenced by the Eval Report.

Week 5 RAG metric         →  Interview Coach analog       threshold
─────────────────────────────────────────────────────────────────────
Faithfulness              →  Rubric Coverage              ≥ 0.70
Answer Relevance          →  Actionability                ≥ 0.70
Context Precision         →  Consistency (delta)          ≤ 0.50
PII Guardrail (Presidio)  →  PII Guardrail (Presidio)     0 leaks
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EvalMetric:
    name: str                    # metric name used in DB + Langfuse
    week5_analog: str            # original Week 5 metric name
    description: str             # what it measures in the interview context
    threshold: Optional[float]   # pass threshold (None = directional)
    direction: str               # "higher_is_better" | "lower_is_better" | "zero"
    source_function: str         # function in eval_layer.py that computes it


METRICS = [
    EvalMetric(
        name="rubric_coverage",
        week5_analog="Faithfulness",
        description=(
            "Fraction of rubric dimensions explicitly addressed in the AI feedback. "
            "Analogous to Week 5 faithfulness: does the output stay grounded in the "
            "provided rubric rather than hallucinating criteria?"
        ),
        threshold=0.70,
        direction="higher_is_better",
        source_function="score_rubric_coverage",
    ),
    EvalMetric(
        name="actionability",
        week5_analog="Answer Relevance",
        description=(
            "Fraction of AI suggestions that contain concrete, actionable language "
            "(imperative verbs, specific examples). Analogous to Week 5 answer "
            "relevance: is the response actually useful to the user's need?"
        ),
        threshold=0.70,
        direction="higher_is_better",
        source_function="score_actionability",
    ),
    EvalMetric(
        name="consistency_delta",
        week5_analog="Context Precision",
        description=(
            "Absolute difference in average score between two sessions on the same "
            "question. Low delta = model is consistent/precise. Analogous to Week 5 "
            "context precision: are the right chunks being used reliably?"
        ),
        threshold=0.50,
        direction="lower_is_better",
        source_function="score_consistency",
    ),
    EvalMetric(
        name="pii_guardrail",
        week5_analog="PII Guardrail",
        description=(
            "Binary pass/fail: did any PII survive into the logged answer or feedback? "
            "Uses Presidio AnalyzerEngine (spaCy en_core_web_lg) with regex fallback "
            "for email/phone/SSN. Reused directly from Week 5 — no changes."
        ),
        threshold=None,
        direction="zero",        # target: 0 leaks
        source_function="redact_pii",
    ),
]


def get_metric(name: str) -> Optional[EvalMetric]:
    return next((m for m in METRICS if m.name == name), None)


def passes_threshold(metric_name: str, value: float) -> bool:
    """Return True if value meets the metric's pass threshold."""
    m = get_metric(metric_name)
    if m is None or m.threshold is None:
        return True  # no threshold → always consider passing
    if m.direction == "higher_is_better":
        return value >= m.threshold
    if m.direction == "lower_is_better":
        return value <= m.threshold
    return True  # "zero" direction handled elsewhere


def print_metric_table():
    """Print the Week 5 → Week 6 metric mapping table (for documentation)."""
    print(f"\n{'Week 5 Metric':<25} {'Week 6 Analog':<22} {'Threshold':<12} {'Direction'}")
    print("-" * 75)
    for m in METRICS:
        threshold_str = (
            f"≥{m.threshold:.0%}" if m.direction == "higher_is_better" and m.threshold
            else f"≤{m.threshold}" if m.direction == "lower_is_better" and m.threshold
            else "0 leaks"
        )
        print(f"{m.week5_analog:<25} {m.name:<22} {threshold_str:<12} {m.direction}")
    print()


if __name__ == "__main__":
    print_metric_table()
