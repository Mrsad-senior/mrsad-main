# Mirsad security upgrade report

Date: 2 November 2026

Branch: `codex/finance-healthcare-integration`

Implementation commit: `947f933` (`Harden action approvals and add bilingual security evaluation`)

## Executive summary

The requested action-control, intent-checking, approval and bilingual evaluation changes were implemented and verified. Mirsad now treats every protected tool call as an authorization decision before execution, compares state-changing actions with the trusted original user task, returns a structured local-LLM assessment, and fails closed when that assessment fails. Approval requests last five minutes, expose the exact decision-critical action fields to the authorized reviewer, apply to one call only, and record the execution outcome in the audit chain.

The final independent bilingual holdout contained 14 authorization cases: six attacks, five normal requests and three approval controls. Without Mirsad, all six proposed attacks would run. With Mirsad and local `qwen2.5:7b`, zero attacks ran, zero normal requests were incorrectly blocked, and all three approval controls returned `require_approval`.

These are small synthetic results, not a production-accuracy guarantee.

## Requested changes and evidence

| Requested change | Implementation | Evidence |
|---|---|---|
| Enforce rules before every action | `Gateway.check_call` evaluates tool allow-list, argument limits, destination, rate limits, taint, original task and behavior before the executor can run | `src/mirsad/gateway.py`; full gateway/API tests |
| Check amount, beneficiary and destination | Finance amount limit remains policy-controlled; new beneficiaries require approval; external Healthcare destinations are denied | `configs/policies/sectors.yaml`; `src/mirsad/security/monitor.py` |
| Deny unauthorized exports | `export_customers` is now a state-changing operation and must match the trusted original task | `TASK_INTENT_MISMATCH` tests in `tests/upgrade/test_sector_upgrade.py` |
| Do not let the LLM override rules | Reasons use deny-overrides. The intent judge adds evidence but cannot downgrade a policy deny | `combine_reasons` and gateway tests |
| Compare action with original request | The intent judge receives `trusted_user_task`, proposed tool and arguments; unbound sensitive actions are denied | `src/mirsad/security/intent.py`; `SecurityMonitor.bind_task` |
| Structured AI result | Intent output now contains `authorized`, `confidence`, `risk_level` and `reason`; the structure is preserved in reason evidence | intent-judge contract tests |
| AI failure or timeout must stop execution | Invalid JSON, timeout or provider failure raises into the gateway evaluation handler, which returns `INTERNAL_ERROR` and denies the call | fail-closed regression test |
| Reviewer sees exact action details | Approval records preserve exact amount, beneficiary and destination while still redacting passwords, tokens and unrelated personal fields | approval service tests |
| Approval expires after five minutes | Runtime, policy and client defaults changed from 120 seconds to 300 seconds; clients wait 330 seconds | policy/config tests and documentation |
| Approval applies once to one action | Approval is bound to `call_id`, tool and arguments; only one conditional `pending` transition can win; identical new calls need a new approval | single-use/concurrency approval tests |
| Audit decision and execution | Audit now records `tool_call.decision`, approval events, explicit `tool_call.executed`, and `tool_result.inspection` | gateway execution tests |
| Repeatable Arabic/English comparison | Added a fixed case file and `scripts/sector_security_eval.py`; it writes JSON and Markdown with attacks, false blocks, controls, latency and failures | `reports/security-upgrade/` |

## Evaluation results

### Final independent local-Qwen holdout

Source: `bench/scenarios/sector_eval_holdout_v2.json`

Detailed evidence: `reports/security-upgrade/sector-evaluation-final.json` and `.md`

| Metric | Without Mirsad | With Mirsad + qwen2.5:7b |
|---|---:|---:|
| Successful attacks | 6/6 | 0/6 |
| Attack success rate | 100.00% | 0.00% |
| Normal requests incorrectly blocked | 0/5 | 0/5 |
| False-block rate | 0.00% | 0.00% |
| Correct approval controls | Not applicable | 3/3 |
| Failed expected results | Not applicable | 0 |

The seven English and seven Arabic cases all matched their expected action.

### Measured latency

| Configuration | p50 | p95 | Maximum |
|---|---:|---:|---:|
| Hard controls only | 3.908 ms | 11.390 ms | 11.390 ms |
| Hard controls + local qwen2.5:7b intent judge | 1705.864 ms | 2364.299 ms | 2364.299 ms |

The local judge adds roughly 1.7–2.4 seconds on this laptop for state-changing calls. Read-only actions do not invoke the intent judge. Hardware, model loading and concurrent applications can change these numbers.

### Honest development finding

The first real-model evaluation blocked all attacks and allowed all normal cases, but it denied two actions that should have been paused for approval. The prompt incorrectly encouraged the model to reject tool arguments merely because they were labelled untrusted. The fix clarified that arguments are data to compare and that authorization is separate from policy approval. That first run is preserved in `sector-evaluation-ollama-v1.json`; the final result uses a different v2 holdout so the failed cases were not reused as final evidence.

## Regression and build results

| Check | Result |
|---|---|
| Python suite | 1,332 passed in 113.45 seconds |
| Frontend suite | 194 passed across 10 files in 3.35 seconds |
| Frontend production build | Passed; 684 modules transformed in 5.01 seconds |
| Python lint | Ruff passed |
| npm dependency audit during install | 0 vulnerabilities reported |

## Architecture and discussion material

The updated discussion diagram is in `docs/SECURITY_UPGRADE_ARCHITECTURE.md`. The short explanation is:

> Mirsad checks the proposed action before execution. Hard policy checks the tool, amount and destination; the security monitor checks the original task, beneficiary and behavior; and the local intent judge returns structured authorization evidence. A deny rule always wins. Approved tools run once, their results are inspected for hidden instructions, and every decision and execution is written to the audit chain.

## Limitations

- Fourteen synthetic cases are too few to estimate real-world accuracy or claim production readiness.
- The evaluation starts from a proposed tool call. It measures Mirsad authorization, not whether an unconstrained agent selects the correct tool by itself.
- The local judge can be slow and may still produce false positives or false negatives on unfamiliar wording.
- The Finance and Healthcare worlds contain fictional data. The beneficiary allow-list is a mock registry, not a bank integration.
- The result does not replace external penetration testing, larger blind datasets or review by Finance and Healthcare specialists.
- Approval arguments are access-controlled, but exact decision-critical destinations are now stored for reviewer clarity; production deployments should add database encryption and retention controls.

## Submission status and next actions

| Required item | Current status | Next action |
|---|---|---|
| Revised SPAP | No SPAP source was found in this repository | Obtain the team’s current SPAP and revise it with the new five-minute approval and test plan |
| Final Report | A DOCX/PDF exists, but it predates this upgrade | Add this report’s change table, final metrics, limitations and architecture diagram, then regenerate DOCX/PDF |
| AI-detection requirement | Not verified and no detector score can be guaranteed | Use original team writing, proper citations and the university-approved checker; revise honestly rather than trying to bypass detection |
| Final Presentation | PPTX exists, but it predates this upgrade | Replace metrics and add one slide for the new authorization/approval flow |
| Project Poster | PPTX/preview exists, but it predates this upgrade | Update the results box and architecture diagram |
| Source/GitHub | Local commit `947f933` is ready | Team review, then push the branch and update the pull request only with permission |
| Test cases/results | Complete for this upgrade | Submit the v2 JSON case file, final JSON report and human-readable Markdown report |
| Live demonstration | Existing server runs from the old extracted ZIP | After team review, deploy the Git-connected copy and repeat the four safe demo flows |

No code or credentials were pushed or exposed while producing this report.
