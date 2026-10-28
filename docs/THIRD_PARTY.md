# Third-party software

Mirsad (Apache-2.0) uses the following open-source runtime components. Development-only tools (pytest, Ruff, Bandit, pip-audit, Vitest, TypeScript, Vite, Playwright, matplotlib, python-docx, python-pptx) are listed in `pyproject.toml` and `web/package.json`.

## Python runtime dependencies

| Package | Version | Licence |
|---|---|---|
| fastapi | 0.143.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| pydantic | 2.14.0 | MIT |
| pydantic-settings | 2.15.0 | MIT |
| pyyaml | 6.0.3 | MIT |
| sqlalchemy | 2.1.4 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| mcp | 2.3.0 | MIT |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| scikit-learn | 1.9.1 | BSD-3-Clause |
| pyjwt | 2.15.1 | MIT |
| sse-starlette | 3.5.0 | BSD-3-Clause |
| click | 8.5.0 | BSD-3-Clause |
| pywebpush | 2.5.0 | MPL-2.0 |
| jsonschema | 4.26.0 | MIT |

## Web runtime dependencies (bundled into `src/mirsad/static`)

| Package | Version | Licence |
|---|---|---|
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-is | 18.3.1 | MIT |
| react-router-dom | 7.18.4 | MIT |
| recharts | 3.10.1 | MIT |

## Models and data

| Item | Use | Licence |
|---|---|---|
| Qwen2.5-7B-Instruct (via Ollama) | Demonstration and benchmark LLM agent (not distributed) | Apache-2.0 (Qwen2.5 7B) |
| deepset/prompt-injections | Optional external English test set for the detector (team download) | Apache-2.0 |
