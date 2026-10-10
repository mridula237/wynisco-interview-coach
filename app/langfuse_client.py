"""
langfuse_client.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Thin wrapper around the Langfuse SDK.
Provides a single initialised client and helper to start a session trace.

Same observability pattern as Week 5:
  Week 5                     →  Interview Coach
  ─────────────────────────────────────────────
  RAG pipeline trace         →  interview session trace
  chunk retrieval span       →  transcription span (audio)
  LLM generation span        →  feedback generation span
  eval scores on trace       →  rubric_coverage / actionability / consistency
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse

    _client = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    LANGFUSE_ENABLED = bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )
except ImportError:
    _client = None
    LANGFUSE_ENABLED = False
    logger.warning("langfuse not installed — observability disabled")


def get_client() -> Optional["Langfuse"]:
    return _client if LANGFUSE_ENABLED else None


def start_trace(
    session_id: str,
    candidate_id: str,
    rubric_id: int,
    input_type: str,
) -> Optional[object]:
    """
    Start a Langfuse trace for one interview session.
    Returns the trace object (or None if Langfuse is disabled).

    The trace ID is stored in the sessions table so every downstream
    span and score can be correlated.
    """
    if not LANGFUSE_ENABLED or _client is None:
        return None
    try:
        trace = _client.trace(
            id=session_id,          # use session UUID as trace ID for easy correlation
            name="interview_session",
            user_id=candidate_id,
            session_id=session_id,
            metadata={
                "rubric_id":  rubric_id,
                "input_type": input_type,
            },
        )
        return trace
    except Exception as e:
        logger.warning(f"Failed to start Langfuse trace: {e}")
        return None


def log_generation(
    trace,
    name: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    input_text: str = "",
    output_text: str = "",
):
    """
    Add a generation span to an existing trace.
    Mirrors the Week 5 pattern of logging each LLM call as a generation.
    """
    if trace is None:
        return
    try:
        trace.generation(
            name=name,
            model=model,
            usage={
                "input":  prompt_tokens,
                "output": completion_tokens,
                "unit":   "TOKENS",
            },
            latency=latency_ms / 1000,  # Langfuse expects seconds
            input=input_text[:2000],    # truncate to avoid oversized payloads
            output=output_text[:2000],
        )
    except Exception as e:
        logger.warning(f"Failed to log generation to Langfuse: {e}")


def flush():
    """Flush buffered events. Call at app shutdown."""
    if LANGFUSE_ENABLED and _client:
        try:
            _client.flush()
        except Exception:
            pass
