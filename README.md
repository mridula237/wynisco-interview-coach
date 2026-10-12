# Wynisco AI Mock Interview Coach

> **Week 6 Capstone — Customer Engineering Sprint**  
> AI/LLM Engineering Program, Wynisco  
> Built by [Mridula Kalaiselvan](https://github.com/mridula237)

An end-to-end AI-powered mock interview coaching system built as a customer-facing POC for a recruiting operations client. Transcribes candidate answers, generates structured rubric-grounded feedback using GPT-4.1-mini, enforces PII guardrails via Presidio, and evaluates output quality with four metrics carried forward from Week 5's RAG eval pipeline. Includes a coach review dashboard for human-in-the-loop oversight.

---

## The Problem

> *"We run 200+ mock interviews a month. Our coaches are overwhelmed giving the same feedback over and over — and candidates still don't know how to fix their answers."*

Recruiting ops teams spend 3–5 hours per coach per week on repetitive mock interview feedback. Quality is inconsistent across coaches, PII from candidate answers gets logged without redaction, and there's no data layer to improve over time.

This POC demonstrates that a GPT-4.1-mini pipeline — with rubric grounding, eval gates, and a human override layer — can cut coach review time by ~60% while improving feedback consistency and auditability.

---

## What It Does

1. **Candidate records an answer** (audio or text) to a behavioral, technical, or leadership question
2. **Whisper API transcribes** the audio in real time
3. **PII is redacted** (Presidio + regex fallback) before anything is stored or logged
4. **GPT-4.1-mini generates structured feedback** — clarity score, depth score, STAR format score, 3 actionable suggestions, red flags
5. **Four eval metrics run automatically** and are logged to Langfuse per session
6. **Coach review dashboard** lets a human approve, override, or reject AI feedback before it reaches the candidate

---

## Architecture

```
Candidate answer (audio / text)
        │
        ▼
Whisper API — transcription
        │
        ▼
PII Redaction — Presidio + regex fallback (email / phone / SSN)
        │
        ▼
GPT-4.1-mini — structured feedback (JSON mode, prompt caching)
   └─ fallback: GPT-4.1-nano on rate-limit or timeout
        │
        ▼
Eval Layer ──────────────────────────────────────────────────────┐
  • Rubric Coverage  (≥ 70%)   ← Week 5: Faithfulness            │
  • Actionability    (≥ 70%)   ← Week 5: Answer Relevance        │
  • Consistency Δ   (≤ 0.5)   ← Week 5: Context Precision       │
  • PII Guardrail   (0 leaks)  ← Week 5: PII Guardrail          │
        │                                                         │
        ▼                                                         │
PostgreSQL ← sessions, feedback, eval_scores, coach_overrides    │
        │                                                         │
        ▼                                                   Langfuse traces
Coach Review Dashboard (Streamlit :8502)                   + scores
  → Approve / Override / Reject
        │
        ▼
Candidate UI (Streamlit :8501) — feedback delivered
```

---

## Week 5 → Week 6 Eval Metric Mapping

The eval layer is a direct carry-forward from the Week 5 RAG pipeline — same structure, adapted to interview coaching.

| Week 5 (RAG Eval) | Week 6 (Interview Coach) | Threshold | Implementation |
|---|---|---|---|
| Faithfulness | **Rubric Coverage** | ≥ 70% | `score_rubric_coverage()` — did feedback address rubric dimensions? |
| Answer Relevance | **Actionability** | ≥ 70% | `score_actionability()` — are suggestions concrete and actionable? |
| Context Precision | **Consistency Δ** | ≤ 0.5 | `score_consistency()` — same question → same score ±0.5? |
| PII Guardrail | **PII Guardrail** | 0 leaks | `redact_pii()` — Presidio + regex, belt-and-suspenders |

```bash
python3 eval/metrics.py          # print the full mapping table
python3 eval/run_eval_batch.py   # re-score historical sessions offline
```

---

## Deliverables

This repo is the working POC artifact. The full capstone submission includes:

| Deliverable | Description |
|---|---|
| **This repo** | Working POC — code, tests, DB schema, rubrics |
| [Eval Report](docs/eval_report.md) | Metrics, pass rates, model comparison, cost per request |
| [Customer Security Brief](docs/security_brief.md) | Data flow, PII handling, retention, audit trail, incident response |
| [Executive Summary](docs/executive_summary.md) | What it does, why now, investment, outcomes, risks, decision needed |
| [Production Readiness Checklist](docs/prod_readiness_checklist.md) | What needs to happen for this POC to go to production |
| Live Demo | 10-minute Loom walkthrough with customer-style narration |

---

## Project Structure

```
wynisco-interview-coach/
├── app/
│   ├── streamlit_app.py        # Candidate UI — record, transcribe, get feedback
│   ├── coach_review.py         # Coach dashboard — approve / override / reject
│   ├── feedback_engine.py      # GPT-4.1-mini feedback generation + fallback
│   ├── eval_layer.py           # 4 eval metrics (Week 5 carry-over)
│   └── langfuse_client.py      # Observability — traces, spans, scores
├── db/
│   ├── schema.sql              # 5 tables: rubrics, sessions, feedback, eval_scores, coach_overrides
│   └── seed.sql                # 3 rubrics: behavioral_star, technical_python, leadership
├── eval/
│   ├── metrics.py              # Week 5 → Week 6 metric definitions (single source of truth)
│   ├── run_eval_batch.py       # Offline batch eval runner
│   └── README.md               # Eval folder docs
├── rubrics/
│   ├── behavioral_star.json    # STAR: situation / task / action / result
│   ├── technical_python.json   # correctness / complexity / clarity / depth
│   └── leadership.json         # vision / influence / decision / outcome
├── tests/
│   ├── conftest.py             # Shared fixtures
│   ├── test_eval_layer.py      # 19 unit tests — rubric coverage, actionability, PII
│   └── test_feedback_engine.py # 10 unit tests — prompt builder, schema, system prompt
├── docs/
│   ├── eval_report.md
│   ├── security_brief.md
│   ├── executive_summary.md
│   └── prod_readiness_checklist.md
├── .env.example                # Environment variable template
├── pytest.ini
├── requirements.txt
└── run.sh                      # One-command launcher
```

---

## Quick Start

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
python3 -m spacy download en_core_web_lg
```

### 2. Configure environment

```bash
cp .env.example .env
# Required: OPENAI_API_KEY, DB_USER, DB_PASSWORD
# Optional: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
```

### 3. Set up the database

```bash
# macOS: brew install postgresql@15 && brew services start postgresql@15
./run.sh db-init
# Creates wynisco DB, runs schema.sql + seed.sql (3 rubrics loaded)
```

### 4. Run the apps

```bash
./run.sh candidate   # → http://localhost:8501  (candidate interview UI)
./run.sh coach       # → http://localhost:8502  (coach review dashboard)
./run.sh both        # run both simultaneously
```

### 5. Run tests

```bash
python3 -m pytest tests/ -v
```

---

## Models

| Role | Model | Reason |
|---|---|---|
| Primary feedback | `gpt-4.1-mini` | Fast, cost-efficient, native JSON mode |
| Fallback | `gpt-4.1-nano` | Kicks in on rate-limit or timeout |
| Transcription | `whisper-1` | OpenAI Whisper API — handles accented speech well |

**Cost per session (estimated):** ~$0.003–0.005 for feedback generation + eval. Whisper adds ~$0.006/min of audio.

---

## Eval Results (POC Run)

| Metric | Target | POC Result |
|---|---|---|
| Rubric Coverage | ≥ 70% | ✅ 87% avg across 3 rubric types |
| Actionability | ≥ 70% | ✅ 92% of suggestions flagged actionable |
| Consistency Δ | ≤ 0.5 | ✅ Avg Δ = 0.21 on repeated questions |
| PII Guardrail | 0 leaks | ✅ 29/29 unit tests pass, 0 leaks in eval run |

---

## Observability

Langfuse traces every session end-to-end:

- **Session trace** — candidate ID, rubric type, question text
- **Generation span** — model used, token count, latency, estimated cost
- **Eval scores** — all 4 metrics logged per session as named scores
- **Coach override flag** — logged when a human changes the AI decision

```bash
# Set in .env to enable — gracefully disabled if not set
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## Offline Batch Eval

Re-score historical feedback against all 4 metrics without re-running the LLM:

```bash
python3 eval/run_eval_batch.py --limit 50    # score last 50 sessions
python3 eval/run_eval_batch.py --rescore     # re-score all historical sessions
python3 eval/run_eval_batch.py --report      # print summary table
```

---

## Security & Data Handling

- **PII redaction** runs before any data touches PostgreSQL or Langfuse — Presidio as primary, regex fallback as safety net
- **No raw audio stored** — Whisper transcription is ephemeral; only redacted text is persisted
- **Coach override audit trail** — every human override is logged to `coach_overrides` table with timestamp and reason
- **OpenAI zero data retention** — recommended for production deployments handling candidate PII
- Full details in [Customer Security Brief](docs/security_brief.md)

---

## Production Path

This is a working POC. To go to production:

1. Replace `.env` secrets → AWS Secrets Manager / Vault
2. Add SSO/OAuth to both UIs
3. Move to managed PostgreSQL (RDS / Supabase)
4. Containerize with Docker + CI/CD via GitHub Actions
5. Enable Langfuse with real keys + cost alerting

Full checklist in [Production Readiness Checklist](docs/prod_readiness_checklist.md).

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | OpenAI API key |
| `DB_HOST` | ✅ | `localhost` | PostgreSQL host |
| `DB_PORT` | | `5432` | PostgreSQL port |
| `DB_NAME` | | `wynisco` | Database name |
| `DB_USER` | ✅ | — | Database user |
| `DB_PASSWORD` | ✅ | — | Database password |
| `LANGFUSE_PUBLIC_KEY` | | — | Langfuse public key (optional) |
| `LANGFUSE_SECRET_KEY` | | — | Langfuse secret key (optional) |
| `LANGFUSE_HOST` | | `https://cloud.langfuse.com` | Langfuse host |

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | OpenAI GPT-4.1-mini / GPT-4.1-nano |
| Transcription | OpenAI Whisper API |
| PII Redaction | Microsoft Presidio + spaCy (`en_core_web_lg`) |
| Database | PostgreSQL + psycopg2 |
| Observability | Langfuse |
| UI | Streamlit (candidate UI + coach dashboard) |
| Testing | pytest — 29 unit tests, no DB/API required |
| Eval | Custom metrics adapted from RAGAS Week 5 pipeline |

---

## About This Project

Built as the Week 6 capstone for Wynisco's AI/LLM Engineering Program. The brief: take a real customer problem in recruiting ops, architect an LLM solution, build a working POC, and deliver it as if presenting to a client.

The eval layer is intentionally continuous with Week 5's RAG eval pipeline — same metric structure, same Langfuse logging pattern, same pass/fail gate logic — demonstrating how evaluation frameworks transfer across LLM application types.

> Score 36+ on the eval rubric → interview-winning portfolio.