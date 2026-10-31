# Mohammed's red-team work

Mohammed Yasser Alanssari — 221110935

This contribution follows the red-team responsibilities in the team roles PDF. The repository's older README assigns different roles; this change does not alter teammates' ownership.

## What is included

- 60 original synthetic attack templates and 60 matched benign invoice tasks.
- Ten cases each for direct overrides, fake authority, hidden text, split instructions, encoded instruction keywords, and Arabic/Arabizi/mixed language.
- Three side-effect goals: a synthetic canary email, an unauthorised fictional transfer, and unauthorised CRM note replacement.
- Fixed pair mapping and a runner that uses the same invoice, user request, seed and injection goal with every defence.
- All five existing defence configurations, with an ideal reviewer and an approve-everything reviewer.
- Existing automated gateway penetration tests plus a fresh dependency scan in GitHub Actions.
- Persistent bypass records, audit verification, decision replay and downloadable raw results.

Run: `PYTHONPATH=.:src python scripts/run_mohammed_redteam.py`.

## Limits

These are scripted, worst-case-compliant agent tests. They do not measure a real model's susceptibility, detector F1, or performance on two models. Benign utility grades reading the document, not the quality of the answer. Split instructions are within one document; encoding affects the instruction keyword rather than the full payload. The canary email is a data-delivery proxy, not proof of customer-data extraction. All fixtures are synthetic and all domains use .example. No real accounts or deployed servers are targeted.

The baseline comparison covers 60 matched cases. The runner repeats them for two reviewer modes and all defence layers. Escalations and final blocks must be reported separately from automatic-denial FPR, because the project harness defines FPR as automatic denials only. The original report's target also counts unnecessary holds.

## Validation status

Measured in [workflow run 41199028383](https://github.com/Mrsad-senior/mrsad-main/actions/runs/41199028383): 174 gateway security checks passed; pip-audit found no known vulnerabilities. All 60 baseline attacks succeeded; 19/60 succeeded under the existing benchmark's full defence (31.7% ASR, 68.3% reduction), in both reviewer modes. The 60 benign twins had 100% tool-completion utility, zero automatic denials and zero escalations. 25/60 benign results were flagged, but none were withheld. The 80% attack-reduction target is not met. All 480 audit-chain checks passed, but replay matched 1,318/1,384 decisions, leaving 66 mismatches. See issues [#4](https://github.com/Mrsad-senior/mrsad-main/issues/4) and [#5](https://github.com/Mrsad-senior/mrsad-main/issues/5). Compact measurements and audit checks are retained under reports/mohammed-redteam; per-case raw episodes and bypasses are in the workflow artifact. The baseline is repeated for each reviewer mode; those rows are duplicate conditions, not independent samples. The detector is rules-only, and the existing full bundle does not test a live LLM judge or the intent check. Any full-defence bypass is retained in `bypasses.json` and should be handed to the blue-team owner with its exact pair ID and raw call outcomes.

The attack text and tooling were prepared with AI assistance, which must be acknowledged according to the team's university policy.
