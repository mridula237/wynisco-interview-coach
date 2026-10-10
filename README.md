# Wynisco AI Mock Interview Coach

An end-to-end AI-powered mock interview coaching system that transcribes candidate answers, generates structured feedback using GPT-4.1-mini, and evaluates output quality with four metrics adapted from Week 5's RAG eval pipeline.

---

## What It Does

1. **Candidate records an answer** (audio or text) to a behavioral, technical, or leadership question
2. **Whisper API transcribes** the audio
3. **PII is redacted** (Presidio + regex fallback) before anything is stored or logged
4. **GPT-4.1-mini generates structured feedback** — clarity, depth, STAR format score, suggestions, red flags
5. **Four eval metrics run automatically** and are logged to Langfuse
6. **Coach review dashboard** lets a human approve, override, or reject AI feedback

---

## Architecture

```
candidate answer (audio/text)
        │
        ▼
  Whisper transcription
        │
        ▼
  PII redaction (Presidio + regex)
        │
        ▼
  GPT-4.1-mini feedback generation
  ├── JSON output mode
  ├── Prompt caching (system prompt + rubric)
  └── GPT-4.1-nano fallback
        │
        ▼
  Eval layer (4 metrics)              Langfuse tracing
  ├── Rubric Coverage (≥70%)    ──►   session trace
  ├── Actionability (≥70%)      ──►   generation span
  ├── Consistency Δ (≤0.5)      ──►   eval scores
  └── PII Guardrail (0 leaks)   ──►
        │
        ▼
  PostgreSQL (5 tables)
        │
        ▼
  Coach Review Dashboard (Streamlit)
```

---

## Week 5 → Week 6 Eval Metric Mapping

| Week 5 (RAG) | Week 6 (Interview Coach) | Threshold | Function |
|---|---|---|---|
| Faithfulness | Rubric Coverage | ≥ 70% | `score_rubric_coverage()` |
| Answer Relevance | Actionability | ≥ 70% | `score_actionability()` |
| Context Precision | Consistency Δ | ≤ 0.5 | `score_consistency()` |
| PII Guardrail | PII Guardrail | 0 leaks | `redact_pii()` |

```bash
python3 eval/metrics.py   # print the full mapping table
```

---

## Project Structure

```
wynisco-interview-coach/
├── app/
│   ├── streamlit_app.py       # Candidate UI — record, transcribe, get feedback
│   ├── coach_review.py        # Coach dashboard — approve / override / reject
│   ├── feedback_engine.py     # GPT-4.1-mini feedback generation
│   ├── eval_layer.py          # 4 eval metrics (Week 5 carry-over)
│   └── langfuse_client.py     # Observability — traces, spans, scores
├── db/
│   ├── schema.sql             # 5 tables: rubrics, sessions, feedback, eval_scores, coach_overrides
│   └── seed.sql               # 3 rubrics: behavioral_star, technical_python, leadership
├── eval/
│   ├── metrics.py             # Week 5 → Week 6 metric definitions (single source of truth)
│   ├── run_eval_batch.py      # Offline batch eval runner (mirrors Week 5 RAG eval pipeline)
│   └── README.md              # Eval folder docs
├── rubrics/
│   ├── behavioral_star.json   # STAR: situation / task / action / result
│   ├── technical_python.json  # correctness / complexity / clarity / depth
│   └── leadership.json        # vision / influence / decision / outcome
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── test_eval_layer.py     # 19 unit tests — rubric coverage, actionability, PII
│   └── test_feedback_engine.py # 10 unit tests — prompt builder, schema, system prompt
├── .env.example               # Environment variable template
├── pytest.ini                 # Test config
├── requirements.txt           # Python dependencies
└── run.sh                     # One-command launcher
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
# Fill in: OPENAI_API_KEY, DB_*, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY
```

### 3. Set up the database

```bash
./run.sh db-init
```

### 4. Run the apps

```bash
./run.sh candidate   # http://localhost:8501 — candidate interview UI
./run.sh coach       # http://localhost:8502 — coach review dashboard
./run.sh both       
```

### 5. Run tests

```bash
python3 -m pytest tests/ -v

```

---

## Models

| Role | Model | Why |
|---|---|---|
| Primary feedback | `gpt-4.1-mini` | Fast, cost-efficient, JSON mode |
| Fallback | `gpt-4.1-nano` | Kicks in on rate-limit or timeout |
| Transcription | `whisper-1` | OpenAI Whisper API |

---

## Observability

Langfuse traces every session end-to-end:
- **Session trace** — candidate ID, rubric, question
- **Generation span** — model, tokens, latency, cost
- **Eval scores** — all 4 metrics logged per session

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env` to enable. Gracefully disabled if not set.

---

## Offline Batch Eval

Re-score historical feedback against all 4 metrics:

```bash
python3 eval/run_eval_batch.py --limit 50    
python3 eval/run_eval_batch.py --rescore     
python3 eval/run_eval_batch.py --report      
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `DB_HOST` | PostgreSQL host (default: localhost) |
| `DB_PORT` | PostgreSQL port (default: 5432) |
| `DB_NAME` | Database name (default: wynisco) |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key (optional) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key (optional) |
| `LANGFUSE_HOST` | Langfuse host (default: https://cloud.langfuse.com) |

---

## Tech Stack

- **LLM**: OpenAI GPT-4.1-mini / GPT-4.1-nano
- **Transcription**: OpenAI Whisper API
- **PII Redaction**: Microsoft Presidio + spaCy
- **Database**: PostgreSQL + psycopg2
- **Observability**: Langfuse
- **UI**: Streamlit
- **Testing**: pytest (29 unit tests)
- **Eval**: Custom metrics adapted from RAGAS Week 5 pipeline