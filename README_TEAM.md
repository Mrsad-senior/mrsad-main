# Mirsad (مرصاد) – Team Guide

**Read this first.** It explains what has been built, how to get and run it, who owns what, what is still
missing and exactly how to finish it before submission. The public project overview is `README.md`.

IS499 Senior Project · Prince Sultan University · Supervisor: Dr. Omaia Al-Omari
Status as of **14 Oct 2026**: system, tests, report, midterm, D2–D6, slides, poster and viva preparation are
complete. **Two results are still pending data that the team must supply** (Section 6).

---

## 1. What Mirsad is (one paragraph for everyone)

Mirsad is a security gateway between an AI agent (an LLM that calls tools such as e-mail, CRM, web,
documents and payments) and those tools. Every tool call is checked **before it runs**: a YAML policy with
per-parameter rules and rate limits, plus *taint tracking*, which notices when data that came from
untrusted content, or confidential data, is about to leave the company. Every tool result is checked
**before the model reads it**: an Arabic/English prompt-injection detector removes or marks hidden
instructions. Risky actions wait for a person to approve them on a phone (an installable web app), and
every decision goes into an HMAC hash-chained audit log that can be verified and replayed. It works with
any LLM through an MCP proxy, an OpenAI-compatible endpoint or a Python SDK.

## 2. Status at a glance

| Item | Status | Where |
|---|---|---|
| Working system (gateway, policy, taint, detector, audit, approvals, API, CLI) | Done | `src/mirsad/` |
| Admin dashboard + approver phone app (English/Arabic, right-to-left) | Done | `web/` (built copy in `src/mirsad/static/`) |
| Demo company workspace + local AI agent (Qwen2.5-7B via Ollama) | Done | `demo/` |
| Benchmark (Mirsad-Bench), including attack-episode support | Done | `bench/` |
| Tests: 1,281 Python + 194 web, all passing; 94.4% coverage | Done | `tests/`, `web/tests/` |
| Security tests (STRIDE suite), Bandit, pip-audit, npm audit: 0 issues | Done | `tests/security/`, `reports/security/` |
| Final report (223 pages), midterm report, D2–D6 (Word + PDF) | Done | `deliverables/` |
| Slides (18, with speaker notes) + CCIS EXPO poster (85 × 142 cm) | Done | `deliverables/` |
| Viva questions and answers per member + demo script | Done | `docs/viva_prep.md` |
| **Detector F1 (Arabic/English)** | **Pending team data** | Section 6 |
| **Attack-success reduction on the benchmark** | **Pending team data** | Section 6 |

The Word documents, slides and poster read every measured number from `reports/results_summary.json`;
values that do not exist yet print as "[pending]" (report) or "pending" (slides, poster). **Typed copies
of numbers also exist** in this file (Sections 2 and 10), `docs/viva_prep.md` (Quick facts and some
answers), `docs/benchmark.md` §6, `docs/detector.md` §13 and `docs/presentation_script.md`; after any
re-run the build owner updates those by hand from `results_summary.json`.

Key measured results (14 Oct 2026):

| Measure | Result | Target |
|---|---|---|
| Benign actions blocked automatically | 0.0% (68 benign calls, 48 tasks, English and Arabic) | ≤ 5% |
| Benign actions sent to a human (by policy design) | 17.6% | – |
| Added latency per tool call (median) | 2.7 ms; 166 ms with 50 concurrent sessions | ≤ 200 ms |
| Audit decisions replayed identically | 272 / 272 per run | 100% |
| Statement coverage | 94.4% | ≥ 80% |

## 3. Getting the project

The project folder is about 120 MB (`deliverables/` is about 87 MB). It is **not yet a Git repository**.

* **Recommended – private GitHub repository** (also makes report §3.4's Git workflow true):
  ```bash
  cd mirsad
  printf '.mirsad*/\n' >> .gitignore
  git init -b main && git add . && git commit -m "Mirsad handoff 14 Oct 2026"
  # create a PRIVATE repository on GitHub, then:
  git remote add origin https://github.com/<owner>/mirsad.git && git push -u origin main
  ```
  Add the other four members as collaborators. Windows users run `git config --global core.autocrlf input`
  before cloning so the shell scripts keep Unix line endings.
* **Alternative – zip** (Google Drive or OneDrive; too large for WhatsApp or e-mail):
  ```bash
  cd .. && zip -r mirsad-2026-10-14.zip mirsad -x 'mirsad/.venv/*' 'mirsad/.mirsad*' 'mirsad/web/node_modules/*' '*/__pycache__/*' '*.DS_Store' 'mirsad/.env'
  ```
  Never share `.mirsad/` (it contains passwords and the audit key).

**Build owner:** one member with a Mac that has Microsoft Word and PowerPoint (proposed: Abdulmalik) keeps
the master copy, runs Section 6.3 and Section 8 rebuilds, and updates `deliverables/`. Everyone else edits
only the source files they own (Section 4), one person per file at a time; announce the file in the group,
then send a pull request or the single changed file. Do not send rebuilt .docx or .pdf files.

## 4. Who owns what (and what to study for the viva)

`docs/viva_prep.md` ("Who answers what" and Part A) is the authority; this table matches it.

| Member | Workstream | Study these files first |
|---|---|---|
| **Bader Alshuraie** (SE) | Gateway core, protocol adapters, policy engine, REST API, CLI, SDK | `src/mirsad/gateway.py`, `src/mirsad/policy/`, `src/mirsad/adapters/`, `src/mirsad/api/`, `src/mirsad/cli.py`, `src/mirsad/sdk/`, `docs/policy-language.md`, `docs/integration.md`, `docs/api.md` |
| **Abdullah Naif Al-Orabi** (SE – AI & DS) | Arabic/English injection detector and dataset | `src/mirsad/detector/`, `docs/detector.md`, `data/detector/` |
| **Bader Abdullah Alyamini** (IS – CYS) | Taint tracking, audit log, approval back end, authentication, database | `src/mirsad/taint/`, `src/mirsad/audit/`, `src/mirsad/storage/`, `src/mirsad/approvals/service.py`, `src/mirsad/approvals/summary.py`, `src/mirsad/auth.py`, `docs/taint-tracking.md`, `docs/audit-and-approvals.md` |
| **Mohammed Yasser Alanssari** (IS – CYS) | Dashboard, approver PWA, notifications | `web/src/` (dashboard/, approver/, shared/), `src/mirsad/approvals/notifier.py`, `docs/web-ui.md` |
| **Abdulmalik bin Saedan** (IS – CYS) | Project management, demo workspace and agent, benchmark, security testing, evidence pipeline | `demo/`, `bench/`, `tests/security/`, `scripts/run_evidence.sh`, `scripts/collect_results.py`, `docs/benchmark.md`, `docs/demo.md`, `docs/pm/plan.yaml` |

Each member reads their section of `docs/viva_prep.md` (11–12 questions with answers that point to the
code) and the 15 general questions.

## 5. Set up and run it

### 5.1 Requirements
* **macOS:** Xcode command-line tools (`xcode-select --install`, gives git and make) and **Python 3.12**
  (`brew install python@3.12` or the python.org installer; Apple's built-in `python3` is usually 3.9, too
  old). Check with `python3.12 --version`.
* **Node.js 20+** (CI uses 22): needed to rebuild the web UI **and** to run `./scripts/run_evidence.sh`,
  `make security` and `make lint`. Run `cd web && npm ci` once (setup does it only if npm is installed).
* Optional, for the live AI demo agent: [Ollama](https://ollama.com) and `ollama pull qwen2.5:7b`
  (about 5 GB download; about 8 GB of free RAM).
* Internet is needed for setup (pip, npm) and for pip-audit/npm audit.

### 5.2 Install (once, 5–10 minutes)
macOS / Linux:
```bash
cd mirsad
chmod +x scripts/*.sh                 # only needed if the folder came through a zip or cloud drive
PYTHON_BIN=python3.12 ./scripts/setup.sh
```
Windows (PowerShell) – demo and tests only; rebuilding documents needs the build owner's Mac:
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\mirsad init --demo          # writes .mirsad\credentials.txt
.venv\Scripts\mirsad serve --demo         # http://127.0.0.1:8700
.venv\Scripts\python -m pytest -m "not llm"
```

### 5.3 Run the demo (macOS / Linux)
```bash
./scripts/run_demo.sh     # first run creates demo users + the demo agent, then starts the server
```
* Dashboard <http://127.0.0.1:8700/> · approver app <http://127.0.0.1:8700/approve> · API docs <http://127.0.0.1:8700/docs>
* **Passwords and the agent key are in `.mirsad/credentials.txt`** (generated, never printed). View it with
  `cat .mirsad/credentials.txt` (in Finder, Cmd+Shift+. shows hidden folders). Log in to the dashboard as
  `admin` and to the approver app as `approver` with the passwords from that file. **Do not delete the
  file** even though its header says so (the demo scripts read it), and never show it on the projector.
* A typeable approver account for the phone: `.venv/bin/mirsad user create mohammed --role approver`
  (asks for the password). Five wrong logins lock a username for five minutes.
* The Demo Console page needs Ollama running with `qwen2.5:7b`.
* Reset everything: stop the server, delete `.mirsad/`, run `./scripts/run_demo.sh` again.
* **Restart the server after rehearsing**: rate limits are kept in memory (bulk export allows 3 calls per
  hour), so repeated rehearsals can cause a `RATE_LIMIT` denial during the real demo.

### 5.4 The live demo for the presentation – choose one
* **Option A (recommended, no LLM needed):** `docs/viva_prep.md` Part C – dashboard tour in English and
  Arabic, an external e-mail paused and approved on the phone, a 200-record export denied by policy, then
  audit verify and replay. Reliable and fast.
* **Option B (Demo Console with the Qwen agent):** the "Live demo run sheet" in
  `docs/presentation_script.md`, which slide 16 and its speaker notes currently describe. Needs Ollama.

If the team chooses Option A, change slide 16 (`s16_demo` in `scripts/build_slides.py`) and the run sheet
to match, then rebuild the slides. Rehearse whichever you choose at least twice on the presentation laptop.

### 5.5 Using a real phone for the approver app
On the presentation laptop the app works at <http://127.0.0.1:8700/approve> (Chrome device mode shows the
phone layout). For a physical phone, use **only a private hotspot that just the laptop and phone join**
(never university or venue Wi-Fi, because this exposes the login page to the network):
```bash
MIRSAD_HOST=0.0.0.0 ./scripts/run_demo.sh      # click "Allow" if macOS asks about incoming connections
ipconfig getifaddr en0                         # the laptop's address (try en1 if empty); open http://<address>:8700/approve on the phone
```
The page works over plain HTTP, but installing to the home screen and push notifications need HTTPS, and
push also needs VAPID keys (report Appendix E.6.3). The live approval list updates without push, which is
enough for the presentation. Stop the server (Ctrl+C) when finished.

### 5.6 Useful commands
```bash
make test         # Python tests + coverage (about 45 s)
make security     # Bandit + pip-audit + npm audit
make bench        # Mirsad-Bench; resumes finished runs (move reports/bench/<run>/ to reports/_superseded/ to re-measure)
make latency      # added-latency benchmark
make detector     # build dataset splits + train the detector
.venv/bin/mirsad --help                              # serve, init, policy, audit, scan, agent, user, mcp-proxy, detector
.venv/bin/mirsad audit verify                        # verify the audit hash chain
.venv/bin/mirsad policy validate configs/policies/default.yaml
```

## 6. What the team must still do: attack-labelled data (most important)

The AI assistant used to build the project is not allowed to write prompt-injection attack examples, so
two results need data **written or sourced by the team**. The code, pipeline, tests and report
placeholders are ready. Use only the fictional company (Najd Trading Co., `.example` addresses, fictional
IBANs and ids); never target real people, systems or services.

| Task | Owner | Reviewer | Due |
|---|---|---|---|
| Detector training batches (English, Arabic) | Abdullah Al-Orabi | | |
| Held-out test batches (written by a different member) | | | |
| Benchmark attack files (injection tasks + templates) | Abdulmalik bin Saedan | | |
| `data/detector/DATASHEET.md` | data authors | | |
| Re-run Section 6.3 and rebuild | build owner | | |

### 6.1 Detector data → Detector F1
1. Write JSON Lines files in `data/detector/raw/`: one JSON object per line with the fields
   `id, text, label, lang, variety, carrier, attack_type, difficulty, source, notes`. Allowed values and
   the labelling guideline: **`docs/detector.md` §11.1–11.4**. `label: 1` = text with an instruction aimed
   at the AI agent; `label: 0` = normal text, including many *hard negatives* (requests to staff,
   articles that describe attacks). Two benign batches already exist (`en-ben.jsonl` 260 lines,
   `ar-ben.jsonl` 100 lines).
2. Put held-out test batches in `data/detector/raw/test-en.jsonl`, `data/detector/raw/test-ar.jsonl`
   (the `lang` field decides the split). Aim for at least 150 records per test language, about half
   positive. Give every record a unique `id` prefixed with its file name (e.g. `test-ar-0001`).
3. Save files as UTF-8 without BOM, one object per line (VS Code works well). After each batch run
   `.venv/bin/python -m mirsad.detector.build_dataset --data data/detector` and fix until it reports
   `invalid lines skipped: 0  warnings: 0` and `leakage check: OK`.
4. Optional external English test set (e.g. `deepset/prompt-injections`, Apache-2.0): convert it to the
   same 10 fields, keep English rows only, and save it as `data/detector/external/test-<name>.jsonl`. The
   `test-` prefix makes it a held-out split; without it the file would be used for training.
5. Create `data/detector/DATASHEET.md`: per file, the author, date and how it was produced (written by
   hand / adapted from a named dataset and licence / with a tool). If any AI tool was used, update report
   §3.6.6 and viva answer G10 to say so.

### 6.2 Benchmark attack files → attack-success reduction
1. Add YAML files to `bench/scenarios/attacks/`. Each file starts with `version: 1` and contains only two
   lists: `injection_tasks` (required `id, category, actions, success`, plus at least one of `goal`,
   `goal_en`, `goal_ar`; optional `vectors, notes`) and `attack_templates` (required `id, lang, style,
   template`; the template must contain `{goal}` and/or `{actions_text}` and may use `{user}` and
   `{model}`; optional `variety, goal_lang, vectors, source, notes`). Allowed values and rules:
   `bench/scenarios/attacks/README.md`, `bench/scenarios/schema.json`, `docs/benchmark.md` §4. Actions
   must be calls to the demo tools; success is judged on the demo world's side effects.
2. Validate: `.venv/bin/python -m bench.loader` (prints errors with file and field), then
   `.venv/bin/python -m bench.loader --has-attacks; echo $?` (0 = ready, 3 = no attack episodes, 1 = invalid).
3. First trial: `ATTACK_LIMIT=50 ./scripts/run_bench.sh`; delete `reports/bench/scripted-attack-*` before
   the real run. The LLM attack run samples `LLM_ATTACK_LIMIT` episodes (default 48) and only runs while
   Ollama is up; quit Ollama to skip it.

### 6.3 Regenerate everything (build owner, in this order)
```bash
make detector                                   # 1. train the detector (seconds to ~1 min)
mkdir -p reports/_superseded/rules-only-benign  # 2. old benign runs were measured rules-only; bench would reuse them
mv reports/bench/scripted-benign-oracle reports/bench/scripted-benign-deny reports/_superseded/rules-only-benign/
(cd web && npm ci)                              # 3. needed for the web tests and npm audit
./scripts/run_evidence.sh                       # 4. tests, scans, latency, benchmark (+ attack runs), results_summary.json
.venv/bin/python scripts/build_slides.py        # 5. slides and poster with the new numbers
.venv/bin/python -m pip install pymupdf
.venv/bin/python scripts/build_poster.py --preview --renderer quicklook
cp deliverables/Mirsad_Poster_preview.png docs/figures/poster-preview.png
.venv/bin/python scripts/preview_slides.py deliverables/Mirsad_Final_Presentation.pptx docs/figures/slides
./scripts/finalize_docs.sh                      # 6. all Word documents + PDFs (about 1 hour; see Section 8)
```
After step 5, rebuild the three slide sheets used by report Appendix D (`docs/figures/slides/sheet-1.png`
… `sheet-3.png`, six slides each), or point Appendix D at the individual `slide-*.png` files.

**Only the numbers update automatically; the sentences around them do not.** After the new results
exist, find every hand-written "pending" or "rules-only" statement and rewrite it to match the measured
values:
```bash
grep -rn -i -E "pending team|pending data|team-supplied|no trained model|no attack (file|episode)|remain pending|not yet|rules-only|why pending" docs/report/content scripts/build_slides.py scripts/build_poster.py
```
At minimum check: both abstracts, report §4.1, §4.2.2, §4.2.3, the Status column of §4.2.9 and the
paragraph under it, §4.2.10, Chapter 5, Appendix B §B.5.8, the D3 SRS, `docs/detector.md` §13,
`docs/benchmark.md` §6.4 and the Quick facts in `docs/viva_prep.md`. If a target is not met, say so
honestly; never edit numbers by hand.

## 7. Before submission – checklist

- [ ] Section 6 done (or the report submitted with the existing explanation of the pending results).
- [ ] Cover pages: in **each** manifest you submit (`docs/report/final_report.yaml`, `midterm_report.yaml`,
      `d2.yaml` … `d6.yaml`) set the `cover.info` row `- [Submission Date, "DD Month 2026"]`. Leave the
      signature and approval-date rows as lines; Dr. Al-Omari signs the printed or PDF copy. Then rebuild.
- [ ] Each member reads and confirms their paragraph in **report §4.3 (Individual and Group Contributions)**.
- [ ] Confirm the **AI-assistance disclosure** (report §3.6.6) matches PSU policy.
- [ ] Optional but valuable: run the stakeholder questionnaire (Appendix F) and the acceptance test (report §3.5) and add the results.
- [ ] Docker check (optional): stop the local server; `cp .env.example .env` and set every value; follow report Appendix E.2.2; `docker compose up -d --build`; open <http://127.0.0.1:8700/healthz> and sign in as admin; `docker compose down`; then rename `.env` to `.env.docker` (a `.env` in the project root changes the local server's secret key). Record pass or fail with the date in report Appendix E and Appendix B.
- [ ] Export the slides and poster to PDF from PowerPoint if a PDF is required (File → Export → PDF).
- [ ] Rehearse the chosen demo (Section 5.4) and restart the server afterwards.

## 8. Editing and rebuilding the documents

All documents are generated. **Edit the sources, never the .docx/.pdf**, or the next rebuild overwrites
your change.

| To change | Edit | Then run |
|---|---|---|
| Report / midterm / D2–D6 text | `docs/report/content/*.md` | `./scripts/finalize_docs.sh` |
| Which chapters go in which document, cover page | `docs/report/*.yaml` | same |
| References (IEEE) | `docs/report/references.yaml` (verified entries; cite with `[@key]`) | same |
| Slides | `scripts/build_slides.py`; speaker notes in `docs/presentation_script.md` | `.venv/bin/python scripts/build_slides.py` |
| Poster | `scripts/build_poster.py` | `.venv/bin/python scripts/build_poster.py` |
| Diagrams | `docs/diagrams/*.mmd`, `*.html` | `MERMAID_JS=<path to mermaid.min.js> .venv/bin/python scripts/render_diagrams.py` (mermaid from `npm install mermaid@11`) |
| Gantt / plan | `docs/pm/plan.yaml` | `.venv/bin/python scripts/make_pm_figures.py` |
| Screenshots | – | `.venv/bin/python scripts/capture_screenshots.py` (needs Google Chrome; overwrites the screenshots used in the report) |

**One source feeds several documents:** the abstracts and Chapters 1–3 go into both the midterm and the
final report; `ch3_3.md` into D4; `ch3_5.md` and `appB_tests.md` into D5; `appE_user_guide.md` into D6;
`parts/*.md` into D3. `finalize_docs.sh` rebuilds all seven. Before the first rebuild, copy any PDF you have
already submitted (e.g. the midterm) to `deliverables/submitted/` and do not re-submit a regenerated copy.

**Do not edit by hand:** `deliverables/*` (generated); `reports/**` including `results_summary.json`
(measured evidence); `data/detector/splits/` and `src/mirsad/detector/model/` (generated by `make detector`);
`src/mirsad/static/` (built from `web/` with `cd web && npm run build`); `docs/figures/*.png` and
`docs/figures/screens/` (generated). Changing `configs/policies/default.yaml` or `bench/scenarios/` changes
the measured results, so re-run Section 6.3 afterwards.

Markdown rules used by the builder: `# Chapter N – Title` starts a chapter; figures
`![Caption](path.png){#fig:label width=6}`; tables start with `Table: Caption {#tab:label}`; references
`@fig:label` / `@tab:label`; citations `[@key]`; measured numbers `{{reports/results_summary.json#path|format}}`.
The full description is at the top of `scripts/build_docs.py`.

**Word automation (`finalize_docs.sh`, macOS + Microsoft Word only):** save and close your own Word
documents first (the script quits Word without saving). On the first run macOS asks whether Terminal may
control Microsoft Word; click OK (to undo a refusal: System Settings → Privacy & Security → Automation).
Allow about one hour for all seven documents and do not use Word meanwhile. If it stalls, the script
restarts Word itself; if it keeps failing, quit Word and run it again. Without a Mac with Word: open each
.docx in Word, press Ctrl+A then F9 to update the contents and lists, and Save As PDF with the same name.

## 9. Decisions taken (and why) – be ready to explain these

| Proposal said | We did | Reason |
|---|---|---|
| Flutter mobile app | Installable web app (PWA) | One code base with the dashboard; Android and iOS without store fees; testable on our machines |
| Fine-tune XLM-RoBERTa / CAMeLBERT | Rules + character n-gram linear model | CPU-only, millisecond latency, small dataset; transformer is future work |
| PostgreSQL + Redis | SQLite by default; PostgreSQL supported and tested; no Redis | Simple setup; Redis is only needed for several replicas |
| Firebase push | Standard Web Push (VAPID) | Open standard, no vendor dependency |
| AgentDojo harness | Own Mirsad-Bench (same method, Arabic scenarios, offline) | AgentDojo is English-only and assumes hosted APIs |
| Burp Suite / ZAP | Automated STRIDE security test suite + Bandit + dependency scans | Repeatable on every change |
| MCP SDK v1 | MCP Python SDK v2 | The current version at build time |

The template requires exactly three SMART objectives; they consolidate the proposal's O1–O6 (report §1.3).

## 10. Honest limitations to mention if asked

* Detector accuracy and attack-success reduction are not yet measured (Section 6).
* The detector currently runs **rules only**; on the existing benign data it flags about 6% of Arabic and 1.2% of English texts (`docs/detector.md` §13.5).
* Taint tracking matches values (addresses, IDs, text fragments); an LLM that paraphrases data can evade it, which is why the policy and approval layers also exist.
* Rate limits live in memory in one process; several replicas would need shared storage.
* The demo scenarios in `demo/scenarios.py` contain example attack text written before the AI assistant's safety stop; they target only the fictional company.
* Docker Compose was not executed on the build machine.
* An AI coding and writing assistant (Anthropic's Claude) was used to build the code, data pipeline, tests and documents; this is disclosed in report §3.6.6. Each member must understand their part (Section 4).

## 11. How long things take

| Step | Time |
|---|---|
| `setup.sh` (internet) | 5–10 min |
| `ollama pull qwen2.5:7b` | about 5 GB download |
| `make test` | about 45 s |
| `run_evidence.sh` without attack data | a few minutes |
| `run_evidence.sh` with attack files | grows with tasks × templates (use `ATTACK_LIMIT`); the LLM attack run takes tens of minutes or more |
| `make detector` | seconds to about 1 min |
| `build_slides.py` / `build_poster.py` | seconds |
| `finalize_docs.sh` (all 7 documents) | about 1 hour |

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| "Python 3.11+ required" during setup | Install Python 3.12, then `PYTHON_BIN=python3.12 ./scripts/setup.sh` |
| `Permission denied` on `./scripts/*.sh` | `chmod +x scripts/*.sh` (or `bash scripts/setup.sh`) |
| Login fails | Use the passwords in `.mirsad/credentials.txt`; after 5 wrong attempts wait 5 minutes |
| Demo Console agent does nothing | Start Ollama and `ollama pull qwen2.5:7b` |
| A call is unexpectedly denied with `RATE_LIMIT` | Restart the server (in-memory limits) |
| Port 8700 in use | `MIRSAD_PORT=8710 ./scripts/run_demo.sh` |
| Web UI changes not visible | `cd web && npm ci && npm run build` |
| `finalize_docs.sh` stalls | Quit Microsoft Word and run it again |
| Documents still show "[pending]" | Expected until Section 6 is done |

## 13. Folder map

```
mirsad/
├── README.md               public overview          ├── README_TEAM.md   this guide
├── deliverables/           report, midterm, D2–D6 (docx + pdf), slides, poster, README with checklist
├── src/mirsad/             gateway, policy, taint, detector, audit, approvals, auth, adapters, sdk, api, cli, static UI
├── web/                    dashboard + approver PWA source (React/TypeScript)
├── configs/                policies/default.yaml, strict-banking.yaml, monitor.yaml; upstreams.yaml
├── demo/                   simulated Najd Trading Co. workspace (MCP server) + demo agent
├── bench/                  Mirsad-Bench harness; scenarios/ (benign tasks), scenarios/attacks/ (team files)
├── data/detector/          raw/ (team data), external/ (optional), splits/ (generated)
├── tests/                  policy, taint, detector, audit, api, adapters, demo, bench, security, integration
├── reports/                results_summary.json, coverage, security scans, benchmark and latency results
├── docs/                   design docs, verified research, report sources, diagrams, figures, viva prep
└── scripts/                setup, demo, evidence, document/slide/poster builders, screenshot capture
```
