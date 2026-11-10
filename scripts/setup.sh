#!/usr/bin/env bash
# Linux/macOS: install backend + frontend dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
(cd frontend && npm ci)
[ -f .env ] || cp .env.example .env
echo "Setup complete. Run scripts/dev.sh"
