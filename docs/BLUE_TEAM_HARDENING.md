# Mirsad: blue-team hardening (2026-10-30)

Owner: Bader Alyamini (blue team). Status: **implemented and tested locally; needs review and merge into the
team repository** (this working copy has no `.git` history).

Work came from incident response on live attack traffic: the demo agent (`qwen2.5:7b` via Ollama) was run
against the built-in scenarios and new, unseen attacks, and every incident in the audit log was triaged.
Each fix below has a regression test, and the full suite passes (`1368 passed, 1 skipped`, `ruff` clean).

## Summary of changes

| # | Finding | Fix | Evidence |
|---|---|---|---|
| 1 | LLM judge talked out of attacks framed as "routine", "pre-approved", "the customer agreed" (detected 0/3 incident payloads, 2/4 held-out) | Second-pass **action extraction** when the judge says benign; configurable `MIRSAD_JUDGE_EXTRACTION=flag\|block\|off` (default `flag`) | `scripts/judge_eval.py`: tuning 0/3 → 3/3, held-out 2/4 → 4/4, known 4/4 → 4/4 |
| 2 | Taint did not link IBANs written with `-` or `.` separators: the untrusted-destination **deny** dropped to approval | `IBAN_RE` accepts `-`/`.` separators; `canonical_iban` strips them | Live probe of 10 disguises: 6/10 → 8/10 linked |
| 3 | The same regex drives audit redaction: dashed IBANs were stored **unmasked** in the audit log | Fixed by #2 | `test_dashed_and_dotted_ibans_are_masked_too` |
| 4 | Intent check accepted the noun "email" as a send request ("Summarise the latest email" authorized `send_email`); "sender" matched "send" | Whole-word verbs; "email"/"reply" count only in command position | 13 new cases in `test_sector_upgrade.py`; live probe now denies |
| 5 | Approval cards hid the key fraud signal (new payee) last, in developer wording; English text inside Arabic cards; "sends data" for payments; `amount_sar`, `10000.0` | Payee status in the first sentence (lock-screen visible); bilingual phrases for all security-monitor codes ranked first; money wording; formatted amounts; named sources (invoice, patient record); no English fallback in Arabic | Before/after on a captured live fraud approval; 26 new summary tests |
| 6 | No positive signal for legitimate payees | Monitor emits informational `KNOWN_BENEFICIARY` (action `allow`) | Card reads "to the registered beneficiary …" |

### Judge evaluation (local `qwen2.5:7b`, `scripts/judge_eval.py`)

| Set | n | Before | After (flagged ≥ 0.5) |
|---|---|---|---|
| Known sector attacks | 4 | 4 | 4 |
| Tuning (missed during incident response) | 3 | 0 | 3 |
| Held-out (written before any change, never tuned on) | 4 | 2 | 4 |
| Benign (60 sampled from `data/detector/raw` + 6 hard negatives) | 66 | 4 | 11 |

In `flag` mode, extraction-only hits are labelled *suspicious* and alerted, but content is still delivered, so
benign content withheld from users stays at 4/66. `block` withholds them (11/66). Only the held-out and benign
rows are an honest estimate, and the sets are small; treat these as indicative, not as F1.

## New blue-team tools

* `scripts/soc_triage.py`: turns the audit log into an incident queue (severity, layers that fired,
  correlated IOCs including masked IBANs `SA…0001`), and `--incident N` prints a full timeline. Read-only.
* `scripts/judge_eval.py`: re-measures the judge on attack, held-out and benign sets after any prompt change.

## Files changed

* `src/mirsad/detector/layered.py`, `src/mirsad/detector/detector.py`, `.env.example`: judge second pass.
* `src/mirsad/textutil.py`, `src/mirsad/taint/extract.py`: IBAN separators (taint and redaction).
* `src/mirsad/security/monitor.py`: send-intent matching, `KNOWN_BENEFICIARY`.
* `src/mirsad/approvals/summary.py`: approval card wording.
* Tests: `tests/upgrade/test_judge_prompt_regression.py`, `test_consolidated_release.py`,
  `test_healthcare_authority_judge.py`, `test_sector_upgrade.py`, `tests/taint/test_taint_extract.py`,
  `tests/audit/test_redaction.py`, `tests/audit/test_approval_summary.py`. Benign judge mocks now answer the
  extraction prompt; a malformed extraction reply fails closed by design.
* `src/mirsad/static/`: rebuilt from `web/` with `npm ci && npm run build` (as `START_HERE_WINDOWS.md` requires).

## Known limitations (not fixed)

* **The agent can repeat injected instructions to the user.** With all tools blocked, a reply still said
  "a refund of 9,900 SAR needs to be issued to SA99…". Mirsad controls tool calls, not the assistant's text;
  a human can still be socially engineered. Mitigation would need an output check on the final reply.
* **An IBAN split across a sentence or spelled out in words** cannot be linked by value-based taint. These
  transfers fall to human approval (`TAINT_UNTRUSTED_TO_EXTERNAL`, `NEW_BENEFICIARY`), not silent execution.
* **Whole-result withholding**: when the detector blocks, the entire document is withheld, including genuine
  content (a real customer complaint, E003, produced no summary).
* **Latency**: each benign judge verdict now costs a second local model call (~0.5 to 1 s).
* **Approver UI**: card text was verified; the `/approve` PWA was not checked visually on a phone. Cards still
  show internal call ids (`read_invoice call_…`), which existing tests require.
* **Rate limits** are counted per agent across sessions; restart the server before a live demo so rehearsals
  do not trip `transfer_funds` limits.

## For discussion with the team

* Finance `transfer_funds` uses `approval: never` below SAR 10,000. Both live Finance attacks chose amounts just
  under the cap (structuring). Today taint and `NEW_BENEFICIARY` escalate those to a human, and
  `test_finance_policy_small_transfer_not_forced_to_approve` shows registered-payee payments are intentionally
  frictionless. Changing it trades fraud margin for approval fatigue; owner: sector packs.
* Red team: please attack the hardened build, starting with the two unlinkable IBAN forms and judge framing.
