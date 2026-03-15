#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  bash scripts/setup_env.sh
fi

.venv/bin/python -m uvicorn middleware.app:app --host 127.0.0.1 --port 8000 --reload
