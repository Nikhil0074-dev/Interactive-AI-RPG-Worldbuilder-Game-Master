#!/usr/bin/env bash
# Linux/macOS: run backend (8000) and frontend (3000) together.
set -euo pipefail
cd "$(dirname "$0")/.."
(cd backend && .venv/bin/python -m uvicorn app.main:create_app --factory --port 8000 --env-file ../.env) &
BACK=$!
trap "kill $BACK" EXIT
(cd frontend && npm run dev)
