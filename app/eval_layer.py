"""
eval_layer.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Eval framework adapted from Week 5 RAG eval metrics:
  Week 5 metric        →  Interview Coach analog
  ─────────────────────────────────────────────────
  Faithfulness         →  Rubric Coverage
  Answer Relevance     →  Actionability
  Context Precision    →  Consistency
  PII Guardrail        →  PII Guardrail (reused directly, via Presidio)

Scores are logged to Langfuse (same tracing pattern as Week 5).
"""

import os
import re
import json
import logging
import psycopg2
import psycopg2.extras
from typing import Optional

logger = logging.getLogger(__name__)

# Thresholds (same approach as Week 5 pass/fail gates)
RUBRIC_COVERAGE_THRESHOLD  = 0.7   # at least 70% of rubric dimensions addressed
ACTIONABILITY_THRESHOLD    = 0.7   # at least 70% of suggestions are actionable
CONSISTENCY_DELTA_MAX      = 0.5   # score drift ≤ 0.5 on repeated same answer


# ---------------------------------------------------------------------------
# 1. Rubric Coverage  (Week 5: Faithfulness)
#    Did the AI feedback address the rubric dimensions?
# ---------------------------------------------------------------------------

def score_rubric_coverage(feedback: dict, rubric_dimensions: list) -> float:
    """
    For each rubric dimension, check whether the feedback summary or
    suggestions mention it. Returns fraction of dimensions covered (0–1).

    Adapted from Week 5 faithfulness check: does the answer stay faithful
    to the retrieved context? Here: does the feedback stay faithful to rubric?
    """
    if not rubric_dimensions:
        return 1.0

    feedback_text = " ".join([
        feedback.get("summary", ""),
        " ".join(feedback.get("suggestions", [])),
        " ".join(feedback.get("red_flags", [])),
    ]).lower()

    covered = 0
    for dim in rubric_dimensions:
        dim_name = dim.get("name", "").lower()
        # Check if dimension name or key terms appear in feedback
        keywords = dim_name.split("_") + dim_name.split(" ")
        if any(kw in feedback_text for kw in keywords if len(kw) > 3):
            covered += 1

    return round(covered / len(rubric_dimensions), 3)


# ---------------------------------------------------------------------------
# 2. Actionability  (Week 5: Answer Relevance)
#    Are the suggestions concrete and actionable?
# ---------------------------------------------------------------------------

ACTIONABILITY_PATTERNS = [
    r"\b(use|try|add|include|structure|start|begin|avoid|replace|show|give|describe|explain|practise|practice)\b",
    r"\b(next time|for example|specifically|concretely|step|action)\b",
    r"\b(instead of|rather than|make sure|ensure)\b",
]

def score_actionability(feedback: dict) -> float:
    """
    Check each suggestion for actionable language.
    Returns fraction of suggestions that are actionable (0–1).

    Adapted from Week 5 answer relevance: is each chunk of retrieved
    context actually relevant to the query? Here: is each suggestion
    actually actionable?
    """
    suggestions = feedback.get("suggestions", [])
    if not suggestions:
        return 0.0

    actionable = 0
    for s in suggestions:
        s_lower = s.lower()
        if any(re.search(p, s_lower) for p in ACTIONABILITY_PATTERNS):
            actionable += 1

    return round(actionable / len(suggestions), 3)


# ---------------------------------------------------------------------------
# 3. Consistency  (Week 5: Context Precision)
#    Same question + same answer → same score ±0.5
# ---------------------------------------------------------------------------

def score_consistency(
    session_id: str,
    question_text: str,
    current_clarity: int,
    current_depth: int,
    current_star: int,
) -> Optional[float]:
    """
    Look up previous feedback for the same question text.
    Returns absolute score delta (lower is better). None if no prior session.

    Adapted from Week 5 context precision: are the retrieved chunks
    precisely the right ones? Here: is the scoring precise/consistent
    across identical inputs?
    """
    try:
        conn = _get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT f.clarity, f.depth, f.star_format
                FROM feedback f
                JOIN sessions s ON s.id = f.session_id
                WHERE s.question_text = %s
                  AND s.id != %s
                ORDER BY f.created_at DESC
                LIMIT 1
                """,
                (question_text, session_id),
            )
            prior = cur.fetchone()
        conn.close()

        if not prior:
            return None

        avg_current = (current_clarity + current_depth + current_star) / 3
        avg_prior   = (prior["clarity"] + prior["depth"] + prior["star_format"]) / 3
        return round(abs(avg_current - avg_prior), 3)

    except Exception as e:
        logger.warning(f"Consistency check failed: {e}")
        return None


# ---------------------------------------------------------------------------
# 4. PII Guardrail  (reused directly from Week 5)
#    Detect PII in candidate answer before logging to Langfuse/DB.
# ---------------------------------------------------------------------------

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    _analyzer  = AnalyzerEngine()
    _anonymizer = AnonymizerEngine()
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    logger.warning("presidio not installed — PII redaction disabled")

# Regex fallback for common PII when Presidio unavailable
_PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
    (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",                    "[PHONE]"),
    (r"\b\d{3}-\d{2}-\d{4}\b",                                 "[SSN]"),
]

def redact_pii(text: str) -> tuple[str, bool]:
    """
    Redact PII from text. Returns (redacted_text, pii_detected: bool).
    Uses Presidio if available, then always applies regex fallback as safety net
    (same as Week 5 pattern — belt-and-suspenders approach).
    """
    redacted = text
    pii_detected = False

    if PRESIDIO_AVAILABLE:
        results = _analyzer.analyze(text=redacted, language="en")
        if results:
            pii_detected = True
            redacted = _anonymizer.anonymize(text=redacted, analyzer_results=results).text

    # Always run regex fallback — catches patterns Presidio misses without en_core_web_lg
    for pattern, replacement in _PII_PATTERNS:
        new_text = re.sub(pattern, replacement, redacted)
        if new_text != redacted:
            pii_detected = True
        redacted = new_text

    return redacted, pii_detected


# ---------------------------------------------------------------------------
# Main eval runner
# ---------------------------------------------------------------------------

def run_eval(
    feedback: dict,
    rubric_dimensions: list,
    question_text: str,
    session_id: str,
    feedback_id: int,
    langfuse_trace=None,
) -> dict:
    """
    Run all four eval checks. Store results in eval_scores table.
    Log scores to Langfuse trace if provided.
    """
    rubric_coverage  = score_rubric_coverage(feedback, rubric_dimensions)
    actionability    = score_actionability(feedback)
    consistency_delta = score_consistency(
        session_id, question_text,
        feedback["clarity"], feedback["depth"], feedback["star_format"]
    )
    _, pii_detected = redact_pii(feedback.get("summary", ""))

    eval_passed = (
        rubric_coverage  >= RUBRIC_COVERAGE_THRESHOLD and
        actionability    >= ACTIONABILITY_THRESHOLD and
        (consistency_delta is None or consistency_delta <= CONSISTENCY_DELTA_MAX)
    )

    scores = {
        "rubric_coverage":   rubric_coverage,
        "actionability":     actionability,
        "consistency_delta": consistency_delta,
        "pii_detected":      pii_detected,
        "eval_passed":       eval_passed,
    }

    # Log to Langfuse (same pattern as Week 5 eval logging)
    if langfuse_trace:
        try:
            langfuse_trace.score(name="rubric_coverage",  value=rubric_coverage)
            langfuse_trace.score(name="actionability",    value=actionability)
            if consistency_delta is not None:
                langfuse_trace.score(name="consistency_delta", value=consistency_delta)
            langfuse_trace.score(name="eval_passed", value=float(eval_passed))
        except Exception as e:
            logger.warning(f"Langfuse score logging failed: {e}")

    # Persist to DB
    _store_eval_scores(feedback_id, scores)

    return scores


def _store_eval_scores(feedback_id: int, scores: dict):
    try:
        conn = _get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO eval_scores
                  (feedback_id, rubric_coverage, actionability,
                   consistency_delta, pii_detected, eval_passed)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    feedback_id,
                    scores["rubric_coverage"],
                    scores["actionability"],
                    scores["consistency_delta"],
                    scores["pii_detected"],
                    scores["eval_passed"],
                ),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to store eval scores: {e}")


def _get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "wynisco"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
