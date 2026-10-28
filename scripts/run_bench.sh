#!/usr/bin/env bash
# Mirsad-Bench: scripted benign episodes for every defence (false positives, friction, utility, latency,
# replay check); when the human team has added attack files to bench/scenarios/attacks/ (see
# bench/scenarios/attacks/README.md), scripted attack runs with the oracle and approve approvers and, if a
# local Ollama model answers, a sampled LLM attack run; then a comparison report of every run made here.
#
# Environment: PY (python, default .venv/bin/python), ATTACK_LIMIT (cap on scripted attack episodes per
# configuration, default: all combinations), LLM_ATTACK_LIMIT (sampled LLM attack episodes, default 48),
# OLLAMA_URL (default http://127.0.0.1:11434).
# The run directory names below are referenced by the report and by scripts/collect_results.py.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
RUNS=(reports/bench/scripted-benign-oracle reports/bench/scripted-benign-deny)

"$PY" -m bench.run --agent scripted --episodes benign --defense all --approver oracle --replay-check \
    --out reports/bench/scripted-benign-oracle
"$PY" -m bench.run --agent scripted --episodes benign --defense all --approver deny --replay-check \
    --out reports/bench/scripted-benign-deny

# Exit codes of `bench.loader --has-attacks`: 0 = attack files define injection tasks and templates,
# 3 = no attack episodes to run, anything else = invalid scenario files (stop here).
set +e
"$PY" -m bench.loader --has-attacks
status=$?
set -e
case "$status" in
  0)
    ATTACK_ARGS=()
    if [[ -n "${ATTACK_LIMIT:-}" ]]; then ATTACK_ARGS+=(--limit "$ATTACK_LIMIT"); fi
    "$PY" -m bench.run --agent scripted --episodes attack --defense all --approver oracle --replay-check \
        ${ATTACK_ARGS[@]+"${ATTACK_ARGS[@]}"} --out reports/bench/scripted-attack-oracle
    "$PY" -m bench.run --agent scripted --episodes attack --defense all --approver approve \
        ${ATTACK_ARGS[@]+"${ATTACK_ARGS[@]}"} --out reports/bench/scripted-attack-approve
    RUNS+=(reports/bench/scripted-attack-oracle reports/bench/scripted-attack-approve)
    if curl -fsS --max-time 3 "$OLLAMA_URL/api/tags" >/dev/null 2>&1; then
      "$PY" -m bench.run --agent llm --episodes attack --defense none,full --approver oracle --replay-check \
          --limit "${LLM_ATTACK_LIMIT:-48}" --llm-base-url "$OLLAMA_URL/v1" --out reports/bench/llm-attack-oracle
      RUNS+=(reports/bench/llm-attack-oracle)
    else
      echo "Ollama is not answering at $OLLAMA_URL: skipping the LLM attack run (reports/bench/llm-attack-oracle)."
    fi
    ;;
  3)
    echo "No attack files in bench/scenarios/attacks/: attack runs skipped, ASR not measured."
    ;;
  *)
    echo "bench.loader reported invalid scenario files (exit $status); fix them before running attacks." >&2
    exit "$status"
    ;;
esac

"$PY" -m bench.compare "${RUNS[@]}" --out reports/bench/comparison.md
