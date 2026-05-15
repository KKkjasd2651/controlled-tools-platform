#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "[setup] create venv"
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "[setup] install deps"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "[setup] copy default .env (mock mode)"
  cp .env.example .env
fi

echo "[run] FastAPI on http://localhost:8000/ui/"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
