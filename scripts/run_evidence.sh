#!/usr/bin/env bash
# Regenerate every piece of evidence used in the report, then reports/results_summary.json.
# Order: Python tests (+coverage, JUnit), web tests, security scans, latency, Mirsad-Bench, detector (if data exists).
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
mkdir -p reports/tests reports/security
"$PY" -m pytest -m "not llm" -p no:cacheprovider --junitxml=reports/tests/junit.xml \
  --cov=mirsad --cov-report=json:reports/coverage.json --cov-report=term | tail -3
(cd web && npx vitest run --reporter=json --outputFile=../reports/tests/vitest.json >/dev/null && echo "web tests done")
"$PY" -m bandit -r src -c pyproject.toml -f json -o reports/security/bandit.json -q || true
"$PY" -m pip_audit --skip-editable -f json -o reports/security/pip-audit.json || true
(cd web && npm audit --json > ../reports/security/npm-audit.json) || true
"$PY" -m bench.latency --out reports/bench/latency.json --figure reports/bench/figures/latency.png
"$PY" -m bench.latency --server-process --out reports/bench/latency-process.json --figure reports/bench/figures/latency-process.png
./scripts/run_bench.sh
if ls data/detector/raw/*.jsonl >/dev/null 2>&1; then
  "$PY" -m mirsad.detector.build_dataset --data data/detector && \
  "$PY" -m mirsad.detector.train --data data/detector --out src/mirsad/detector/model --reports reports
fi
"$PY" scripts/collect_results.py
