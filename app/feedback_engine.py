"""
feedback_engine.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Fetches the rubric from PostgreSQL, calls GPT-4.1-mini with JSON output mode,
returns structured feedback. Prompt caching applied to system prompt + rubric.
Falls back to GPT-4.1-nano on rate-limit or quota errors.
"""

import os
import json
import time
import logging
from typing import Optional

import psycopg2
import psycopg2.extras
from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PRIMARY_MODEL  = "gpt-4.1-mini"
FALLBACK_MODEL = "gpt-4.1-nano"

FEEDBACK_SCHEMA = {
    "type": "object",
    "properties": {
        "clarity":     {"type": "integer", "minimum": 1, "maximum": 5},
        "depth":       {"type": "integer", "minimum": 1, "maximum": 5},
        "star_format": {"type": "integer", "minimum": 1, "maximum": 5},
        "red_flags":   {"type": "array",   "items": {"type": "string"}},
        "suggestions": {"type": "array",   "items": {"type": "string"}},
        "summary":     {"type": "string"},
    },
    "required": ["clarity", "depth", "star_format", "red_flags", "suggestions", "summary"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are an expert interview coach evaluating candidate answers for Wynisco.

Your job:
1. Read the rubric dimensions provided.
2. Score the candidate's answer on clarity, depth, and star_format (1-5 each).
3. Identify red_flags (weaknesses that must be addressed).
4. Provide actionable suggestions (each must have a concrete next step).
5. Write a short summary (2-3 sentences).

Scoring guide:
  5 = Excellent, exceeds expectations
  4 = Good, meets expectations
  3 = Adequate, some gaps
  2 = Below expectations, significant gaps
  1 = Poor, does not meet expectations

Be direct and constructive. Every suggestion must be specific and actionable.
Return ONLY valid JSON matching the schema provided — no extra text."""


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "wynisco"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def fetch_rubric(rubric_id: int) -> dict:
    """Fetch rubric dimensions from PostgreSQL."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT name, question_type, dimensions FROM rubrics WHERE id = %s", (rubric_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Rubric {rubric_id} not found")
            return dict(row)


def build_user_prompt(question: str, answer: str, rubric: dict) -> str:
    dims = json.dumps(rubric["dimensions"], indent=2)
    return f"""RUBRIC ({rubric['question_type']} question):
{dims}

QUESTION:
{question}

CANDIDATE ANSWER:
{answer}

Evaluate the answer against the rubric and return structured feedback as JSON."""


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str,
    client: OpenAI,
) -> tuple[dict, dict]:
    """Call OpenAI with JSON output mode. Returns (parsed_json, usage_dict)."""
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.3,
    )
    content = response.choices[0].message.content
    usage = {
        "prompt_tokens":     response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "model":             model,
    }
    return json.loads(content), usage


def generate_feedback(
    question: str,
    answer: str,
    rubric_id: int,
    session_id: str,
    client: Optional[OpenAI] = None,
) -> dict:
    """
    Main entry point. Returns feedback dict with scores, red_flags,
    suggestions, latency, token counts, and model used.
    """
    if client is None:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    rubric = fetch_rubric(rubric_id)

    # Prompt caching: system_prompt + rubric are static per rubric_id
    # OpenAI automatically caches prompts >1024 tokens; we structure
    # system prompt + rubric as one block to maximise cache hits.
    system_with_rubric = (
        SYSTEM_PROMPT
        + f"\n\nRUBRIC DIMENSIONS FOR THIS SESSION:\n{json.dumps(rubric['dimensions'], indent=2)}"
    )

    user_prompt = build_user_prompt(question, answer, rubric)

    model_used = PRIMARY_MODEL
    t0 = time.time()

    try:
        result, usage = call_llm(system_with_rubric, user_prompt, PRIMARY_MODEL, client)
    except Exception as e:
        logger.warning(f"Primary model failed ({e}), falling back to {FALLBACK_MODEL}")
        model_used = FALLBACK_MODEL
        result, usage = call_llm(system_with_rubric, user_prompt, FALLBACK_MODEL, client)

    latency_ms = int((time.time() - t0) * 1000)

    return {
        "session_id":         session_id,
        "clarity":            result["clarity"],
        "depth":              result["depth"],
        "star_format":        result["star_format"],
        "red_flags":          result["red_flags"],
        "suggestions":        result["suggestions"],
        "summary":            result["summary"],
        "raw_response":       result,
        "model_used":         model_used,
        "latency_ms":         latency_ms,
        "prompt_tokens":      usage["prompt_tokens"],
        "completion_tokens":  usage["completion_tokens"],
    }


def store_feedback(feedback: dict) -> int:
    """Persist feedback to PostgreSQL. Returns feedback row id."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO feedback
                  (session_id, clarity, depth, star_format, red_flags,
                   suggestions, raw_response, model_used, latency_ms,
                   prompt_tokens, completion_tokens)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    feedback["session_id"],
                    feedback["clarity"],
                    feedback["depth"],
                    feedback["star_format"],
                    json.dumps(feedback["red_flags"]),
                    json.dumps(feedback["suggestions"]),
                    json.dumps(feedback["raw_response"]),
                    feedback["model_used"],
                    feedback["latency_ms"],
                    feedback["prompt_tokens"],
                    feedback["completion_tokens"],
                ),
            )
            feedback_id = cur.fetchone()[0]
        conn.commit()
    return feedback_id
