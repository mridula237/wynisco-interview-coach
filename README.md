# Wynisco AI Mock Interview Coach

**Week 6 Capstone — Working POC**

An AI-powered interview coaching system that gives candidates structured, rubric-driven feedback on their answers. Built with GPT-4.1-mini, Whisper, Streamlit, PostgreSQL, and Langfuse.

---

## Architecture

```
Candidate
    │
    ├── text answer ──────────────────────────────────┐
    └── audio upload → Whisper API (transcription)    │
                                                      ▼
                                            Feedback Engine
                                     (GPT-4.1-mini · JSON output mode)
                                     (Prompt caching: system + rubric)
                                                      │
                                                      ▼
                                              Eval Layer
                                   rubric_coverage · actionability · consistency
                                   PII guardrail (Presidio)
                                                      │
                                                      ▼
                                          Coach Review UI
                                   approve · override · reject
                                                      │
                                                      ▼
                                          Candidate Report
                                                      │
                              ┌───────────────────────┘
                              ▼                       ▼
                          Langfuse                PostgreSQL
                    (traces · scores)      (sessions · rubrics · feedback)
```

---

## Week 5 Eval Metrics Reused

| Week 5 Metric      | Interview Coach Analog | Threshold |
|--------------------|------------------------|-----------|
| Faithfulness       | Rubric Coverage        | ≥ 70%     |
| Answer Relevance   | Actionability          | ≥ 70%     |
| Context Precision  | Consistency            | delta ≤ 0.5 |
| PII Guardrail      | PII Guardrail (Presidio) | —       |

---

## Files

```
wynisco-interview-coach/
├── db/
│   ├── schema.sql          # PostgreSQL tables (5 tables)
│   └── seed.sql            # Sample rubrics (behavioral STAR, technical, leadership)
├── app/
│   ├── feedback_engine.py  # GPT-4.1-mini feedback generation + prompt caching
│   ├── eval_layer.py       # Week 5 eval metrics + PII guardrail
│   ├── langfuse_client.py  # Observability wrapper
│   ├── streamlit_app.py    # Candidate UI
│   └── coach_review.py     # Coach dashboard (override tracking)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/<your-org>/wynisco-interview-coach.git
cd wynisco-interview-coach
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # for Presidio PII detection
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your OpenAI key, Postgres creds, and Langfuse keys
```

### 3. Initialise the database

```bash
psql -U postgres -c "CREATE DATABASE wynisco;"
psql -U postgres -d wynisco -f db/schema.sql
psql -U postgres -d wynisco -f db/seed.sql
```

### 4. Run the candidate UI

```bash
streamlit run app/streamlit_app.py
```

### 5. Run the coach review dashboard

```bash
streamlit run app/coach_review.py --server.port 8502
```

---

## Success Gates

| Metric                  | Target          |
|-------------------------|-----------------|
| Feedback latency        | < 2 min         |
| Coach override rate     | ≤ 30%           |
| Average feedback score  | ≥ 4.0 / 5       |
| Cost per session        | < $0.10         |
| Rubric coverage         | ≥ 70%           |
| Actionability           | ≥ 70%           |

---

## Cost Estimate

- GPT-4.1-mini: ~$0.0015 per session (≈800 prompt tokens, 250 completion)
- Whisper: ~$0.006/min of audio
- Total: **~$0.002–$0.008 per session** (well under $0.10 target)

---

## Deploy

**Railway (recommended)**:
```bash
railway init
railway add postgresql
railway up
```

**Render**: Add a `render.yaml` with two services (streamlit_app, coach_review) and a PostgreSQL instance.

---

## Author

Mridula Kalaiselvan — Wynisco Week 6 Capstone
