#!/usr/bin/env bash
# Start Mirsad with the simulated Najd Trading workspace and the demo agent.
# Prerequisite for the live LLM agent: Ollama running with `ollama pull qwen2.5:7b`.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
export MIRSAD_DATA_DIR="${MIRSAD_DATA_DIR:-.mirsad}"
export MIRSAD_ENABLE_DEMO=true
if [ ! -f "$MIRSAD_DATA_DIR/credentials.txt" ]; then
  "$PY" -m mirsad.cli init --demo
fi
echo "Demo credentials are stored in $MIRSAD_DATA_DIR/credentials.txt (not printed)."
echo "Dashboard:    http://127.0.0.1:8700/"
echo "Approver app: http://127.0.0.1:8700/approve"
exec "$PY" -m mirsad.cli serve
