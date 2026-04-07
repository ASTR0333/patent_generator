#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-/opt/patent_generator}"
REDIS_URL_VALUE="${REDIS_URL:-redis://127.0.0.1:6379/0}"

cd "$PROJECT_DIR"

if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

if [[ ! -d "frontend/node_modules" ]]; then
  cd frontend
  npm install
  cd ..
fi

cd frontend
npm run build
cd ..

screen -S patent_backend -X quit || true
screen -S patent_frontend -X quit || true

screen -dmS patent_backend bash -lc "cd '$PROJECT_DIR' && source .venv/bin/activate && REDIS_URL='$REDIS_URL_VALUE' uvicorn backend.main:app --host 127.0.0.1 --port 8000"
screen -dmS patent_frontend bash -lc "cd '$PROJECT_DIR/frontend' && npm run preview -- --host 127.0.0.1 --port 4173"

echo "Started screens:"
screen -ls | grep patent_ || true
