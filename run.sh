#!/usr/bin/env bash
# run.sh — convenience launcher for Wynisco AI Interview Coach
# Usage:
#   ./run.sh candidate     → starts candidate UI on port 8501
#   ./run.sh coach         → starts coach dashboard on port 8502
#   ./run.sh both          → starts both in background
#   ./run.sh test          → runs unit tests (no DB/API needed)
#   ./run.sh db-init       → creates DB and runs schema + seed

set -e
cd "$(dirname "$0")"

# Load .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

case "$1" in
  candidate)
    echo "Starting candidate UI → http://localhost:8501"
    streamlit run app/streamlit_app.py --server.port 8501
    ;;
  coach)
    echo "Starting coach dashboard → http://localhost:8502"
    streamlit run app/coach_review.py --server.port 8502
    ;;
  both)
    echo "Starting candidate UI  → http://localhost:8501"
    echo "Starting coach dashboard → http://localhost:8502"
    streamlit run app/streamlit_app.py --server.port 8501 &
    streamlit run app/coach_review.py --server.port 8502 &
    echo "Both running. Press Ctrl+C to stop."
    wait
    ;;
  test)
    echo "Running unit tests (no DB or API required)…"
    pytest tests/ -v
    ;;
  db-init)
    echo "Initialising database…"
    DB_NAME="${DB_NAME:-wynisco}"
    DB_USER="${DB_USER:-postgres}"
    psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || echo "DB may already exist — continuing."
    psql -U "$DB_USER" -d "$DB_NAME" -f db/schema.sql
    psql -U "$DB_USER" -d "$DB_NAME" -f db/seed.sql
    echo "Done. Tables created and rubrics seeded."
    ;;
  *)
    echo "Usage: ./run.sh [candidate|coach|both|test|db-init]"
    exit 1
    ;;
esac
