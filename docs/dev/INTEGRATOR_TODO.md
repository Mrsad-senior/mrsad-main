# Integrator checklist (claims that must be verified before the documents are final)

- [ ] Requirements: NFR9 coverage ≥ 80% — measure; adjust text if not met.
- [ ] Requirements: NFR11 ≥ 50 concurrent sessions — measure in latency benchmark or reword.
- [ ] NFR5 docker compose — Docker is not available on the build machine; state clearly what was and was not executed.
- [ ] FR6.3 "100% of benchmark decisions replay to the same action" — run a replay sweep over a benchmark audit DB.
- [ ] Ch1 SMART objectives: fill achieved numbers in Ch4 success-criteria table from real runs only.
- [ ] Bibliography keys used in content must exist in docs/report/references.yaml (built from verified research output).
- [ ] Every screenshot in Appendix C must come from the real running system.

## Cross-module wiring to verify after the api-finish agent (from area agents' integration notes)
- [ ] gateway.inspect_result: call taint.register_result with the ORIGINAL result (before sanitising).
- [ ] gateway.check_call: audit payload stores taint.minimal_snapshot(...) (full snapshot ~390 KB exceeds 20k payload cap → replay breaks).
- [ ] create_app: TaintTracker(internal_domains=lambda: app.state.gateway.policy.internal_domains()).
- [ ] approval_required(taint_fired=...) should count only taint reasons whose action != ALLOW.
- [ ] ApprovalService(org_name=policy organization name); periodic approvals.expire_overdue(); await approvals.aclose() on shutdown; no double Web Push from api.
- [ ] Duplicate LoginThrottle (api/routers/auth.py vs mirsad.auth) → keep one.
- [ ] Policy store: re-activating a YAML whose semantic version already exists must reuse the row (no PK conflict).
- [ ] CORS allow_headers includes X-Upstream-Authorization and X-Mirsad-Session.
- [ ] Bench: fresh RateLimiter per episode (shared limits distort FPR).
- [ ] demo/agent.py embeds DEMO_POLICY_YAML: keep in sync with configs/policies/default.yaml or load the file.
- [ ] ST-13: gateway returns raw upstream exception text to the agent; return a safe message (keep ToolArgumentError/validation messages), log details server-side.

## Resume point (paused at user request)
- [ ] Docs workflow stopped while 3 writers were still running: check docs/report/content/ch4_implementation_evaluation.md is complete,
      scripts/build_slides.py + deliverables/Mirsad_Final_Presentation.pptx, scripts/build_poster.py + deliverables/Mirsad_Poster.pptx,
      docs/viva_prep.md and docs/presentation_script.md; finish whatever is missing.
- [ ] Bench: implement attack-episode execution (load team files from bench/scenarios/attacks/, plant rendered template into the task's
      `reads` target, ScriptedAgent obeys surviving content, success predicates on world side effects); tests with neutral placeholder
      templates only. run_bench.sh must write runs named scripted-attack-oracle, scripted-attack-approve, llm-attack-oracle when attack files exist.
- [x] Placeholder run names normalised to scripted_attack_oracle / scripted_attack_approve / llm_attack_oracle.
- [ ] Appendix D from exported slide/poster images; run scripts/finalize_docs.sh (Word: restart it first if it hangs).
- [ ] Final review pass (rubric critics), then the final summary to the user.

## Progress 2026-10-14
- [x] ch4 complete; slides rebuilt in Arial (fit check clean, previews via scripts/preview_slides.py — Quick Look hangs on
      python-pptx speaker notes, so previews drop notes); poster rebuilt with current results; viva prep written.
- [x] Bench attack-episode execution implemented (bench/attacks.py, 69 bench tests); run names scripted-attack-oracle /
      scripted-attack-approve / llm-attack-oracle.
- [x] Default + monitor policy now scan CRM results; demo agent loads configs/policies/default.yaml; mcp>=2.0; collector fix.
- [x] Evidence regenerated: 1,281 py tests, 194 web, 94.4% coverage, 0 scan issues, 166 ms p50 @50 sessions.
- [x] Appendix D written (poster preview + 3 slide sheets).
- [x] Review workflow (critics + fixer) — then build all docs and run scripts/finalize_docs.sh (Word: quit/restart if it hangs;
      each large document can take ~10+ min). PowerPoint/Keynote AppleScript exports hang here; deliver pptx + Quick Look previews.
- [x] Final summary to the user.

## Final state 2026-10-14
- [x] 135 review findings applied; all 7 Word documents built and finalised by Word (TOCs filled, PDFs verified: correct title
      pages). Final report 223 pages, midterm 91, D2 25, D3 29, D4 38, D5 46, D6 27.
- [x] web/node_modules removed to keep the folder small (restore with `cd web && npm ci`).
- Remaining for the team: see deliverables/README.md ("Before submitting").
