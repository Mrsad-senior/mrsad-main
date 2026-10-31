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

Execution results will be recorded after the pull-request workflow finishes. Do not claim attack-success reduction, a clean dependency scan, or complete penetration testing before inspecting that evidence. Any full-defence bypass is retained in `bypasses.json` and should be handed to the blue-team owner with its exact pair ID and raw call outcomes.

The attack text and tooling were prepared with AI assistance, which must be acknowledged according to the team's university policy.
