"""
streamlit_app.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Candidate-facing UI:
  - Paste a question + type or upload audio answer
  - Runs feedback_engine → eval_layer
  - Displays feedback score card
  - Logs session + trace to Langfuse
"""

import os
import uuid
import tempfile
import logging

import streamlit as st
from openai import OpenAI
import psycopg2
import psycopg2.extras

from feedback_engine import generate_feedback, store_feedback, fetch_rubric
from eval_layer import run_eval, redact_pii

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Langfuse (optional — graceful no-op if not configured)
# ---------------------------------------------------------------------------
try:
    from langfuse import Langfuse
    _lf = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    LANGFUSE_ENABLED = True
except Exception:
    _lf = None
    LANGFUSE_ENABLED = False


def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "wynisco"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def load_rubrics() -> list[dict]:
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, name, question_type FROM rubrics ORDER BY name")
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Could not load rubrics: {e}")
        return []


def transcribe_audio(audio_bytes: bytes, client: OpenAI) -> str:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    with open(tmp_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
    os.unlink(tmp_path)
    return transcript.text


def store_session(candidate_id, question, answer, input_type, rubric_id, trace_id) -> str:
    session_id = str(uuid.uuid4())
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions
                  (id, candidate_id, question_text, answer_text, input_type,
                   rubric_id, langfuse_trace_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (session_id, candidate_id, question, answer,
                 input_type, rubric_id, trace_id),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to store session: {e}")
    return session_id


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Wynisco Interview Coach",
    page_icon="🎯",
    layout="centered",
)

st.title("Wynisco AI Interview Coach")
st.caption("Get structured feedback on your interview answers — powered by GPT-4.1-mini")

# ---------------------------------------------------------------------------
# Sidebar: candidate ID + rubric selector
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Session Setup")
    candidate_id = st.text_input(
        "Candidate ID (anonymous)",
        value=st.session_state.get("candidate_id", f"cand_{uuid.uuid4().hex[:8]}"),
        help="Used for tracking; does not need to be your real name.",
    )
    st.session_state["candidate_id"] = candidate_id

    rubrics = load_rubrics()
    if rubrics:
        rubric_options = {r["name"]: r["id"] for r in rubrics}
        selected_rubric_name = st.selectbox("Rubric", list(rubric_options.keys()))
        selected_rubric_id = rubric_options[selected_rubric_name]
    else:
        st.warning("No rubrics found. Seed the DB first.")
        selected_rubric_id = 1
        selected_rubric_name = "default"

    st.divider()
    st.caption(f"Langfuse: {'✅ connected' if LANGFUSE_ENABLED else '⚠️ disabled'}")

# ---------------------------------------------------------------------------
# Main form
# ---------------------------------------------------------------------------
question = st.text_area(
    "Interview Question",
    placeholder="e.g. Tell me about a time you led a project under a tight deadline.",
    height=80,
)

st.subheader("Your Answer")
input_mode = st.radio("Input mode", ["Type answer", "Upload audio"], horizontal=True)

answer_text = ""
input_type = "text"

if input_mode == "Type answer":
    answer_text = st.text_area("Answer", height=180,
                               placeholder="Write your full answer here…")
else:
    audio_file = st.file_uploader(
        "Upload audio (.mp3, .wav, .webm, .m4a)",
        type=["mp3", "wav", "webm", "m4a"],
    )
    if audio_file:
        st.audio(audio_file)
        input_type = "audio"

submit = st.button("Get Feedback", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------
if submit:
    if not question.strip():
        st.warning("Please enter an interview question.")
        st.stop()

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    with st.spinner("Processing…"):
        # 1. Transcribe if audio
        if input_type == "audio":
            if not audio_file:
                st.error("Please upload an audio file.")
                st.stop()
            answer_text = transcribe_audio(audio_file.read(), client)
            st.info(f"**Transcript:** {answer_text}")

        if not answer_text.strip():
            st.warning("Answer is empty — nothing to evaluate.")
            st.stop()

        # 2. PII redaction before any logging
        safe_answer, pii_found = redact_pii(answer_text)
        if pii_found:
            st.warning("⚠️ PII detected in your answer — redacted before logging.")

        # 3. Start Langfuse trace
        trace = None
        trace_id = None
        if LANGFUSE_ENABLED and _lf:
            try:
                trace = _lf.trace(
                    name="interview_session",
                    user_id=candidate_id,
                    metadata={
                        "rubric_id": selected_rubric_id,
                        "input_type": input_type,
                    },
                )
                trace_id = trace.id
            except Exception as e:
                logger.warning(f"Langfuse trace init failed: {e}")

        # 4. Store session (with redacted answer)
        session_id = store_session(
            candidate_id, question, safe_answer,
            input_type, selected_rubric_id, trace_id,
        )

        # 5. Generate feedback
        feedback = generate_feedback(
            question=question,
            answer=safe_answer,
            rubric_id=selected_rubric_id,
            session_id=session_id,
            client=client,
        )
        feedback_id = store_feedback(feedback)

        # 6. Run eval layer
        rubric = fetch_rubric(selected_rubric_id)
        eval_scores = run_eval(
            feedback=feedback,
            rubric_dimensions=rubric.get("dimensions", []),
            question_text=question,
            session_id=session_id,
            feedback_id=feedback_id,
            langfuse_trace=trace,
        )

        if trace and LANGFUSE_ENABLED:
            try:
                trace.score(name="latency_ms", value=feedback["latency_ms"])
            except Exception:
                pass

    # ---------------------------------------------------------------------------
    # Display results
    # ---------------------------------------------------------------------------
    st.success(f"Feedback generated in {feedback['latency_ms']}ms "
               f"using `{feedback['model_used']}`")

    # Score card
    col1, col2, col3 = st.columns(3)
    col1.metric("Clarity", f"{feedback['clarity']}/5")
    col2.metric("Depth", f"{feedback['depth']}/5")
    col3.metric("STAR Format", f"{feedback['star_format']}/5")

    avg_score = (feedback["clarity"] + feedback["depth"] + feedback["star_format"]) / 3
    st.progress(avg_score / 5, text=f"Overall: {avg_score:.1f}/5")

    # Summary
    st.subheader("Summary")
    st.write(feedback["summary"])

    # Red flags
    if feedback.get("red_flags"):
        with st.expander("🚩 Red Flags", expanded=True):
            for flag in feedback["red_flags"]:
                st.markdown(f"- {flag}")

    # Suggestions
    if feedback.get("suggestions"):
        with st.expander("💡 Suggestions for Improvement", expanded=True):
            for sug in feedback["suggestions"]:
                st.markdown(f"- {sug}")

    # Eval badge
    with st.expander("Eval Scores (Week 5 metrics)"):
        ecol1, ecol2, ecol3 = st.columns(3)
        ecol1.metric("Rubric Coverage", f"{eval_scores['rubric_coverage']:.0%}")
        ecol2.metric("Actionability", f"{eval_scores['actionability']:.0%}")
        delta_label = (
            f"Δ {eval_scores['consistency_delta']:.2f}"
            if eval_scores["consistency_delta"] is not None
            else "First run"
        )
        ecol3.metric("Consistency", delta_label)
        if eval_scores["eval_passed"]:
            st.success("✅ All eval checks passed")
        else:
            st.error("❌ One or more eval checks failed — flagged for coach review")

    st.caption(f"Session ID: `{session_id}` | "
               f"Tokens: {feedback['prompt_tokens']}p / {feedback['completion_tokens']}c")
