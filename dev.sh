#!/usr/bin/env bash
# Start backend (simulator) + frontend dev server. Ctrl-C stops both.
set -e
cd "$(dirname "$0")"
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000 &
BACK=$!
trap 'kill $BACK' EXIT
npm --prefix frontend run dev
