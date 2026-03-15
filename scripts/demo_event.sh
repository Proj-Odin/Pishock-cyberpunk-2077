#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  bash scripts/setup_env.sh
fi

.venv/bin/python -m middleware.demo_event "$@"
