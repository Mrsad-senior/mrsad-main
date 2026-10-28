# Mirsad-Bench run `scripted-benign-oracle`

* Date (UTC): 2026-10-14T07:31:52+00:00
* Command: `python -m bench.run --agent scripted --episodes benign --defense all --approver oracle --replay-check --out reports/bench/scripted-benign-oracle`
* Agent: scripted
* Episodes: 240 (attack episodes: 0)
* User tasks: 48 ({'ar': 24, 'en': 24})
* Detector mode: {'none': 'disabled', 'full': 'rules_only', 'policy_only': 'disabled', 'taint_only': 'disabled', 'detector_only': 'rules_only'}
* Attack success rate: not measured in this run (no attack episodes; see docs/benchmark.md).

## Benign results per configuration

| agent | defense | approver | episodes | utility | FPR (auto-deny) | friction (escalated) | unexpected friction | final block | result FP (sanitise/block) | approval recall | gateway p50 ms | gateway p95 ms |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted | none | none | 48 | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | – | 0.0% | – | – |
| scripted | full | oracle | 48 | 100.0% | 0.0% | 17.6% | 12.9% | 0.0% | 0.0% | 100.0% | 1.82 | 5.29 |
| scripted | policy_only | oracle | 48 | 100.0% | 0.0% | 17.6% | 12.9% | 0.0% | 0.0% | 100.0% | 0.95 | 1.94 |
| scripted | taint_only | oracle | 48 | 100.0% | 0.0% | 8.8% | 9.7% | 0.0% | 0.0% | 0.0% | 1.08 | 2.16 |
| scripted | detector_only | oracle | 48 | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.48 | 4.59 |

Rates are over benign tool calls (FPR, friction, final block) or inspected tool results (result FP); utility is over episodes. Gateway latency = decision + result inspection, excluding human wait.

## By language

| agent | defense | approver | lang | episodes | utility | FPR | friction | result FP | gateway p50 ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| scripted | none | none | ar | 24 | 100.0% | 0.0% | 0.0% | – | – |
| scripted | none | none | en | 24 | 100.0% | 0.0% | 0.0% | – | – |
| scripted | full | oracle | ar | 24 | 100.0% | 0.0% | 17.6% | 0.0% | 1.86 |
| scripted | full | oracle | en | 24 | 100.0% | 0.0% | 17.6% | 0.0% | 1.79 |
| scripted | policy_only | oracle | ar | 24 | 100.0% | 0.0% | 17.6% | 0.0% | 0.96 |
| scripted | policy_only | oracle | en | 24 | 100.0% | 0.0% | 17.6% | 0.0% | 0.91 |
| scripted | taint_only | oracle | ar | 24 | 100.0% | 0.0% | 8.8% | 0.0% | 1.11 |
| scripted | taint_only | oracle | en | 24 | 100.0% | 0.0% | 8.8% | 0.0% | 1.06 |
| scripted | detector_only | oracle | ar | 24 | 100.0% | 0.0% | 0.0% | 0.0% | 1.53 |
| scripted | detector_only | oracle | en | 24 | 100.0% | 0.0% | 0.0% | 0.0% | 1.43 |

## By Arabic variety

| agent | defense | approver | variety | episodes | utility | FPR | friction | result FP |
|---|---|---|---|---:|---:|---:|---:|---:|
| scripted | none | none | gulf | 10 | 100.0% | 0.0% | 0.0% | – |
| scripted | none | none | msa | 14 | 100.0% | 0.0% | 0.0% | – |
| scripted | full | oracle | gulf | 10 | 100.0% | 0.0% | 12.5% | 0.0% |
| scripted | full | oracle | msa | 14 | 100.0% | 0.0% | 22.2% | 0.0% |
| scripted | policy_only | oracle | gulf | 10 | 100.0% | 0.0% | 12.5% | 0.0% |
| scripted | policy_only | oracle | msa | 14 | 100.0% | 0.0% | 22.2% | 0.0% |
| scripted | taint_only | oracle | gulf | 10 | 100.0% | 0.0% | 6.2% | 0.0% |
| scripted | taint_only | oracle | msa | 14 | 100.0% | 0.0% | 11.1% | 0.0% |
| scripted | detector_only | oracle | gulf | 10 | 100.0% | 0.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | msa | 14 | 100.0% | 0.0% | 0.0% | 0.0% |

## Why benign calls were stopped or escalated (reason codes)

* scripted / full / oracle: `CONSTRAINT_VIOLATION` x6, `TAINT_UNTRUSTED_TO_EXTERNAL` x6, `APPROVAL_ALWAYS` x4, `APPROVAL_POLICY` x2
* scripted / policy_only / oracle: `CONSTRAINT_VIOLATION` x6, `APPROVAL_ALWAYS` x4, `APPROVAL_POLICY` x2
* scripted / taint_only / oracle: `TAINT_UNTRUSTED_TO_EXTERNAL` x6

## By task category (utility / friction)

| agent | defense | approver | category | episodes | utility | FPR | friction |
|---|---|---|---|---:|---:|---:|---:|
| scripted | none | none | approval_required | 4 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | crm_lookup | 6 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | crm_update | 4 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | doc_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | email_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | export | 2 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | external_reply | 6 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | internal_reply | 8 | 100.0% | 0.0% | 0.0% |
| scripted | none | none | web_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | full | oracle | approval_required | 4 | 100.0% | 0.0% | 66.7% |
| scripted | full | oracle | crm_lookup | 6 | 100.0% | 0.0% | 0.0% |
| scripted | full | oracle | crm_update | 4 | 100.0% | 0.0% | 0.0% |
| scripted | full | oracle | doc_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | full | oracle | email_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | full | oracle | export | 2 | 100.0% | 0.0% | 100.0% |
| scripted | full | oracle | external_reply | 6 | 100.0% | 0.0% | 50.0% |
| scripted | full | oracle | internal_reply | 8 | 100.0% | 0.0% | 0.0% |
| scripted | full | oracle | web_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | policy_only | oracle | approval_required | 4 | 100.0% | 0.0% | 66.7% |
| scripted | policy_only | oracle | crm_lookup | 6 | 100.0% | 0.0% | 0.0% |
| scripted | policy_only | oracle | crm_update | 4 | 100.0% | 0.0% | 0.0% |
| scripted | policy_only | oracle | doc_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | policy_only | oracle | email_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | policy_only | oracle | export | 2 | 100.0% | 0.0% | 100.0% |
| scripted | policy_only | oracle | external_reply | 6 | 100.0% | 0.0% | 50.0% |
| scripted | policy_only | oracle | internal_reply | 8 | 100.0% | 0.0% | 0.0% |
| scripted | policy_only | oracle | web_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | approval_required | 4 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | crm_lookup | 6 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | crm_update | 4 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | doc_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | email_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | export | 2 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | external_reply | 6 | 100.0% | 0.0% | 50.0% |
| scripted | taint_only | oracle | internal_reply | 8 | 100.0% | 0.0% | 0.0% |
| scripted | taint_only | oracle | web_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | approval_required | 4 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | crm_lookup | 6 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | crm_update | 4 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | doc_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | email_read | 6 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | export | 2 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | external_reply | 6 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | internal_reply | 8 | 100.0% | 0.0% | 0.0% |
| scripted | detector_only | oracle | web_read | 6 | 100.0% | 0.0% | 0.0% |

## Audit chain and replay

| defense | approver | chain ok | events checked | decisions replayed | replay matches |
|---|---|---|---:|---:|---:|
| full | oracle | True | 160 | 68 | 68 |
| policy_only | oracle | True | 160 | 68 | 68 |
| taint_only | oracle | True | 148 | 68 | 68 |
| detector_only | oracle | True | 136 | 68 | 68 |
