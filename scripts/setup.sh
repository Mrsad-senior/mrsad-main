#!/usr/bin/env bash
# One-time developer setup: Python 3.11+ virtual environment, backend + dev dependencies, web deps.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
command -v "$PYTHON_BIN" >/dev/null || PYTHON_BIN=python3
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
if command -v npm >/dev/null; then
  (cd web && npm ci)
else
  echo "npm not found: skipping web dependencies (the prebuilt UI in src/mirsad/static still works)"
fi
echo "Setup complete. Next: ./scripts/run_demo.sh"
