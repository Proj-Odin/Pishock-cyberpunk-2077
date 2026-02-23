#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
cp -n middleware/config.example.yaml middleware/config.yaml || true
echo "Environment ready"
