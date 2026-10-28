# Common developer tasks. Run `make setup` once, then e.g. `make test` or `make demo`.
PY ?= .venv/bin/python
NPM ?= npm

.PHONY: setup web test test-all lint security serve demo bench latency detector docs diagrams clean

setup:            ## create .venv, install backend + dev deps, install web deps
	./scripts/setup.sh

web:              ## build dashboard + approver PWA into src/mirsad/static
	cd web && $(NPM) ci && $(NPM) run build

test:             ## fast test suite (no LLM)
	$(PY) -m pytest -m "not llm" --cov=mirsad --cov-report=term-missing

test-all:         ## includes tests that call the local Ollama model
	$(PY) -m pytest --cov=mirsad

lint:
	$(PY) -m ruff check src tests demo bench scripts
	cd web && npx tsc --noEmit

security:         ## SAST + dependency audit
	$(PY) -m bandit -q -r src -c pyproject.toml
	$(PY) -m pip_audit --skip-editable
	cd web && $(NPM) audit --omit=dev

serve:
	$(PY) -m mirsad.cli serve

demo:             ## initialise demo users/agent and start the gateway with the demo workspace
	./scripts/run_demo.sh

bench:            ## scripted Mirsad-Bench (all defences) + comparison report
	./scripts/run_bench.sh

latency:
	$(PY) -m bench.latency

detector:         ## rebuild dataset splits and retrain the detector
	$(PY) -m mirsad.detector.build_dataset --data data/detector
	$(PY) -m mirsad.detector.train --data data/detector --out src/mirsad/detector/model --reports reports

diagrams:         ## needs MERMAID_JS=path/to/mermaid.min.js
	$(PY) scripts/render_diagrams.py
	$(PY) scripts/make_pm_figures.py

docs:             ## build the Word deliverables (then scripts/finalize_docs.sh for PDF on macOS + Word)
	$(PY) scripts/build_docs.py docs/report/*.yaml

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
