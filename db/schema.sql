-- Wynisco AI Mock Interview Coach
-- PostgreSQL schema v1

-- Rubrics: question type → evaluation dimensions
CREATE TABLE IF NOT EXISTS rubrics (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,          -- e.g. "behavioral_star", "technical_python"
    question_type TEXT NOT NULL,               -- "behavioral" | "technical"
    dimensions  JSONB NOT NULL,                -- [{name, description, weight}]
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions: one row per candidate interview session
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id    TEXT NOT NULL,             -- anonymised candidate identifier
    question_text   TEXT NOT NULL,
    answer_text     TEXT NOT NULL,             -- transcript (from Whisper if audio)
    input_type      TEXT NOT NULL DEFAULT 'text', -- "text" | "audio"
    rubric_id       INTEGER REFERENCES rubrics(id),
    langfuse_trace_id TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback: AI-generated structured feedback per session
CREATE TABLE IF NOT EXISTS feedback (
    id              SERIAL PRIMARY KEY,
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    clarity         INTEGER CHECK (clarity BETWEEN 1 AND 5),
    depth           INTEGER CHECK (depth BETWEEN 1 AND 5),
    star_format     INTEGER CHECK (star_format BETWEEN 1 AND 5),
    red_flags       JSONB DEFAULT '[]',        -- list of strings
    suggestions     JSONB DEFAULT '[]',        -- list of strings
    raw_response    JSONB,                     -- full LLM JSON output
    model_used      TEXT,                      -- "gpt-4.1-mini" | "gpt-4.1-nano"
    latency_ms      INTEGER,
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Eval scores: Week-5-style eval metrics applied to each feedback
CREATE TABLE IF NOT EXISTS eval_scores (
    id                  SERIAL PRIMARY KEY,
    feedback_id         INTEGER REFERENCES feedback(id) ON DELETE CASCADE,
    rubric_coverage     FLOAT CHECK (rubric_coverage BETWEEN 0 AND 1),  -- faithfulness analog
    actionability       FLOAT CHECK (actionability BETWEEN 0 AND 1),    -- relevance analog
    consistency_delta   FLOAT,                                           -- |score - baseline| for same Q
    pii_detected        BOOLEAN DEFAULT FALSE,
    eval_passed         BOOLEAN,                                         -- all metrics above threshold
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Coach overrides: tracks every coach edit/approval
CREATE TABLE IF NOT EXISTS coach_overrides (
    id              SERIAL PRIMARY KEY,
    feedback_id     INTEGER REFERENCES feedback(id) ON DELETE CASCADE,
    coach_id        TEXT NOT NULL,
    field_overridden TEXT,                     -- NULL means full approval, else "clarity"|"depth" etc.
    original_value  JSONB,
    new_value       JSONB,
    action          TEXT NOT NULL,             -- "approve" | "override" | "reject"
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_candidate ON sessions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_feedback_session   ON feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_eval_feedback      ON eval_scores(feedback_id);
CREATE INDEX IF NOT EXISTS idx_overrides_feedback ON coach_overrides(feedback_id);
