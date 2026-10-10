"""
coach_review.py
Wynisco AI Mock Interview Coach — Week 6 Capstone

Coach-facing UI:
  - Lists pending sessions where eval failed or override is needed
  - Coach can approve, edit individual fields, or reject the AI feedback
  - Every action is logged to coach_overrides table
  - Override rate is reported and tracked against ≤30% target
"""

import os
import json
import logging

import streamlit as st
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "wynisco"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def load_pending_reviews() -> list[dict]:
    """Load sessions with feedback that has not been reviewed OR failed eval."""
    try:
        conn = get_db()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    s.id          AS session_id,
                    s.candidate_id,
                    s.question_text,
                    s.answer_text,
                    s.input_type,
                    s.created_at  AS session_at,
                    f.id          AS feedback_id,
                    f.clarity,
                    f.depth,
                    f.star_format,
                    f.red_flags,
                    f.suggestions,
                    f.summary     AS ai_summary,
                    f.model_used,
                    f.latency_ms,
                    e.rubric_coverage,
                    e.actionability,
                    e.consistency_delta,
                    e.pii_detected,
                    e.eval_passed,
                    co.id         AS override_id
                FROM sessions s
                JOIN feedback f ON f.session_id = s.id
                LEFT JOIN eval_scores e ON e.feedback_id = f.id
                LEFT JOIN coach_overrides co ON co.feedback_id = f.id
                WHERE co.id IS NULL          -- not yet reviewed
                ORDER BY s.created_at DESC
                LIMIT 50
                """,
            )
            rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Failed to load pending reviews: {e}")
        return []


def load_override_rate() -> dict:
    """Calculate overall override rate for the dashboard."""
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE action = 'override') AS overrides,
                    COUNT(*) FILTER (WHERE action = 'approve')  AS approvals,
                    COUNT(*) FILTER (WHERE action = 'reject')   AS rejections,
                    COUNT(*)                                     AS total
                FROM coach_overrides
                """
            )
            row = cur.fetchone()
        conn.close()
        total    = row[3] or 0
        override = row[0] or 0
        approve  = row[1] or 0
        reject   = row[2] or 0
        rate = (override + reject) / total if total else 0.0
        return {"overrides": override, "approvals": approve,
                "rejections": reject, "total": total, "rate": rate}
    except Exception as e:
        logger.error(f"Override rate query failed: {e}")
        return {"overrides": 0, "approvals": 0, "rejections": 0, "total": 0, "rate": 0.0}


def save_override(feedback_id: int, coach_id: str, action: str,
                  field: str | None, original, new_value):
    try:
        conn = get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO coach_overrides
                  (feedback_id, coach_id, field_overridden,
                   original_value, new_value, action)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    feedback_id,
                    coach_id,
                    field,
                    json.dumps(original),
                    json.dumps(new_value),
                    action,
                ),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save override: {e}")


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Wynisco Coach Review",
    page_icon="🧑‍🏫",
    layout="wide",
)

st.title("Coach Review Dashboard")
st.caption("Review AI-generated feedback, approve or override, track quality metrics.")

# ---------------------------------------------------------------------------
# Sidebar: coach login + stats
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Coach")
    coach_id = st.text_input("Coach ID", value="coach_001")

    st.divider()
    st.subheader("Override Rate")
    stats = load_override_rate()
    rate_pct = stats["rate"] * 100
    color = "normal" if rate_pct <= 30 else "inverse"
    st.metric(
        "Override + Reject Rate",
        f"{rate_pct:.1f}%",
        delta=f"Target ≤ 30%",
        delta_color=color,
    )
    st.caption(f"Approved: {stats['approvals']} | "
               f"Overrides: {stats['overrides']} | "
               f"Rejected: {stats['rejections']} | "
               f"Total: {stats['total']}")

    if st.button("🔄 Refresh"):
        st.rerun()

# ---------------------------------------------------------------------------
# Pending review list
# ---------------------------------------------------------------------------
pending = load_pending_reviews()

if not pending:
    st.success("🎉 No sessions pending review.")
    st.stop()

st.subheader(f"{len(pending)} session(s) pending review")

for row in pending:
    eval_flag = not row.get("eval_passed", True)
    header_label = (
        f"{'🔴 Eval Failed · ' if eval_flag else ''}"
        f"{row['candidate_id']} · "
        f"{str(row['session_at'])[:16]} · "
        f"Session {str(row['session_id'])[:8]}…"
    )

    with st.expander(header_label, expanded=eval_flag):
        c1, c2 = st.columns([3, 2])

        with c1:
            st.markdown(f"**Question:** {row['question_text']}")
            st.markdown(f"**Answer ({row['input_type']}):** {row['answer_text'][:500]}"
                        + ("…" if len(row["answer_text"]) > 500 else ""))
            st.markdown(f"**AI Summary:** {row['ai_summary']}")

            if row.get("red_flags"):
                flags = row["red_flags"] if isinstance(row["red_flags"], list) \
                        else json.loads(row["red_flags"])
                st.markdown("**Red Flags:** " + " · ".join(flags))

            if row.get("suggestions"):
                sugs = row["suggestions"] if isinstance(row["suggestions"], list) \
                       else json.loads(row["suggestions"])
                st.markdown("**Suggestions:**")
                for s in sugs:
                    st.markdown(f"- {s}")

        with c2:
            st.markdown("**AI Scores**")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Clarity",    row["clarity"])
            mc2.metric("Depth",      row["depth"])
            mc3.metric("STAR",       row["star_format"])

            st.markdown("**Eval Scores**")
            ec1, ec2 = st.columns(2)
            ec1.metric("Rubric Cov.",
                       f"{row['rubric_coverage']:.0%}" if row.get("rubric_coverage") is not None else "—")
            ec2.metric("Actionability",
                       f"{row['actionability']:.0%}" if row.get("actionability") is not None else "—")

            if row.get("pii_detected"):
                st.warning("⚠️ PII was detected and redacted")
            if not row.get("eval_passed"):
                st.error("❌ Eval failed — review required")

            st.divider()
            st.markdown("**Override fields (optional)**")
            new_clarity   = st.slider(f"Clarity",    1, 5, int(row["clarity"]),
                                      key=f"clarity_{row['feedback_id']}")
            new_depth     = st.slider(f"Depth",      1, 5, int(row["depth"]),
                                      key=f"depth_{row['feedback_id']}")
            new_star      = st.slider(f"STAR Format",1, 5, int(row["star_format"]),
                                      key=f"star_{row['feedback_id']}")
            coach_note    = st.text_area("Coach note (optional)", key=f"note_{row['feedback_id']}")

            bcol1, bcol2, bcol3 = st.columns(3)

            if bcol1.button("✅ Approve", key=f"approve_{row['feedback_id']}"):
                save_override(
                    feedback_id=row["feedback_id"],
                    coach_id=coach_id,
                    action="approve",
                    field=None,
                    original=None,
                    new_value={"note": coach_note},
                )
                st.success("Approved!")
                st.rerun()

            if bcol2.button("✏️ Override", key=f"override_{row['feedback_id']}"):
                changed_fields = {}
                if new_clarity != row["clarity"]:
                    changed_fields["clarity"] = {"from": row["clarity"], "to": new_clarity}
                if new_depth != row["depth"]:
                    changed_fields["depth"]   = {"from": row["depth"],   "to": new_depth}
                if new_star != row["star_format"]:
                    changed_fields["star_format"] = {"from": row["star_format"], "to": new_star}

                if not changed_fields and not coach_note:
                    st.warning("No changes made. Adjust a slider or add a note to override.")
                else:
                    save_override(
                        feedback_id=row["feedback_id"],
                        coach_id=coach_id,
                        action="override",
                        field=",".join(changed_fields.keys()) or None,
                        original={k: v["from"] for k, v in changed_fields.items()},
                        new_value={k: v["to"]   for k, v in changed_fields.items()}
                                  | {"note": coach_note},
                    )
                    st.success(f"Override saved for: {', '.join(changed_fields) or 'note only'}")
                    st.rerun()

            if bcol3.button("🗑️ Reject", key=f"reject_{row['feedback_id']}"):
                save_override(
                    feedback_id=row["feedback_id"],
                    coach_id=coach_id,
                    action="reject",
                    field=None,
                    original=None,
                    new_value={"reason": coach_note or "Rejected by coach"},
                )
                st.error("Feedback rejected.")
                st.rerun()
