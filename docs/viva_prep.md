# Mirsad (مرصاد) – Viva Preparation

IS499 Senior Project · Prince Sultan University · Supervisor: Dr. Omaia Al-Omari

This document prepares the team for the committee's questions and the live demonstration. The rubric item it targets is **"answers reflect student understanding"**: the committee wants to hear each of us explain *our own* design decisions, their limits and where they live in the code. Read your own section until you can answer without notes. Before the viva, open each file cited in your section and be ready to walk through it on screen.

**Ground rules for every answer**

1. Answer the question first in one or two sentences, then give the reason, then (if asked) point to the code.
2. Every number comes from `reports/results_summary.json` (generated 14 Oct 2026, after the benchmark was re-run under the current default policy). If the evidence is re-run before the viva, re-check the numbers below against that file. Never round a number in a way that changes its meaning, and never estimate one that is not there.
3. The detector F1 score and the attack-success reduction are **pending team data**. Say so plainly and explain why (general question G8). Do not guess a value.
4. Describe attacks only in general terms ("instructions hidden in an e-mail that tell the agent to send data outside"). Do not read out or improvise attack text.
5. If you do not know, say what you would check and where (e.g. "that is decided in `combine_reasons` in `src/mirsad/models.py`; I would need to confirm the tie-breaking there").

## Quick facts (from `reports/results_summary.json`)

| Item | Value |
|---|---|
| Python tests | 1,281 of 1,281 pass (adapters 78, api 185, audit 240, bench 68, demo 72, detector 227, integration 8, policy 265, security 45, taint 93) |
| Web tests | 194 of 194 pass in 10 test files (38 Vitest suites) |
| Statement coverage (core package) | 94.4% of 9,763 statements |
| Static and dependency scans | Bandit 0 issues in 13,023 lines; pip-audit 0 vulnerable of 124 packages; npm audit 0 vulnerabilities |
| Mirsad-Bench (scripted, benign, oracle approver) | 48 tasks (24 English, 24 Arabic), 68 tool calls |
| Benign false-positive rate, full defence | 0.0% (target ≤ 5%) |
| Approval friction, full defence | 17.6% (12 of 68 calls sent to a human); taint-only 8.8%; policy-only 17.6%; detector-only 0% |
| Utility, full defence | 100% with the oracle approver; 75% with an approver who denies everything |
| Audit replay | 272 of 272 decisions replayed to the same action in each scripted run; 6 of 6 in the LLM smoke run; chains verified after every configuration |
| Added latency, separate server process, 1,000 calls | sequential median 2.7 ms (p95 6.0 ms); 50 concurrent sessions median 166 ms (p95 208 ms, p99 216 ms), 291 requests/s, 0 errors |
| Added latency, server in the load generator's process | 50 concurrent sessions median 205 ms, p95 880 ms: above 200 ms, because client and server compete for one interpreter; NFR1 is judged on the separate-process layout |
| Detector mode during all measurements | rules-only (no trained model is packaged yet) |
| Detector F1 (Arabic / English) | pending team data |
| Attack-success reduction | pending team data |

## Who answers what

| Topic | First answer | Back-up |
|---|---|---|
| Gateway pipeline, adapters (MCP, OpenAI proxy, Guard API, SDK), policy language, REST API, CLI | Bader Alshuraie | Abdulmalik bin Saedan |
| Injection detector, normalisation, rules, model, dataset, Arabic handling | Abdullah Naif Al-Orabi | Bader Abdullah Alyamini |
| Taint tracking, audit log, redaction, replay, approval back end | Bader Abdullah Alyamini | Bader Alshuraie |
| Dashboard, approver PWA, i18n/RTL, accessibility, notifications | Mohammed Yasser Alanssari | Abdullah Naif Al-Orabi |
| Mirsad-Bench, latency benchmark, demo workspace and agent, security testing, project management | Abdulmalik bin Saedan | Mohammed Yasser Alanssari |

---

## Part A – Questions by workstream

### A.1 Bader Alshuraie – gateway core, adapters, policy engine

You own `src/mirsad/gateway.py`, `src/mirsad/policy/`, `src/mirsad/adapters/`, `src/mirsad/sdk/`, `src/mirsad/api/` and `src/mirsad/cli.py`.

**Q1. Walk us through what happens to one tool call.**
`Gateway.check_call` (`gateway.py`) runs `_decide` in a worker thread under one re-entrant lock. `_evaluate` asks the policy engine (`PolicyEngine.evaluate_call` in `policy/engine.py`) for its reasons in a fixed order: unknown agent → deny; tool not allowed → deny; the tool's own risk (informational); argument constraints; rate limit; global rules; `approval: always`. Then the taint tracker adds its reasons. `combine_reasons` (`models.py`) merges them by deny-overrides, and `approval_required` adds a human step for an otherwise allowed call when the policy says so. The decision, with the call, the reasons, a minimal taint snapshot and the rate counts, is appended to the audit log as `tool_call.decision`. If approval is needed, `_await_human` creates an approval and waits. `execute` then runs the tool (with a 120 s executor timeout) and passes the result through `inspect_result` before the agent sees it.

**Q2. What does "fail closed" mean in your code, concretely?**
Any failure that could let an unchecked action through turns into a denial. An exception while evaluating → `DENY` with code `INTERNAL_ERROR`. The audit append fails while enforcing → `DENY` with `AUDIT_UNAVAILABLE` ("no audit trail, no action"). The approval service fails → `APPROVAL_UNAVAILABLE`, denied. The detector crashes on an untrusted result → the result is withheld (`SCAN_FAILED`). The Python SDK raises instead of running the tool if the gateway is unreachable (`sdk/client.py`). The cost is availability: if Mirsad is down, protected agents stop, which is the intended trade-off for a security control.

**Q3. Why deny-overrides, and how is it implemented?**
`combine_reasons` takes the most severe action across all reasons (allow < require_approval < deny) and the maximum risk score. One layer's objection can never be outvoted by another layer's approval, and the result does not depend on the order in which layers run. That property is what makes it safe to add layers.

**Q4. How do you version and change a policy while the gateway runs?**
The version is the SHA-256 of the canonical JSON of the *parsed* document (`canonical_json` in `policy/engine.py`), so comments and whitespace do not create new versions. `PUT /api/policies` validates and activates; `POST /api/policies/{version}/activate` rolls back to any stored version (`api/routers/policies.py`). `Gateway.set_policy` swaps the engine atomically; calls already being evaluated keep the engine they started with. Every stored version stays in the policy store so replay can rebuild the exact engine that made an old decision (`Gateway._engine_for`).

**Q5. A policy is written by an administrator. How do you stop a bad policy from hurting the gateway?**
Three defences. The YAML loader rejects duplicate keys that YAML would otherwise silently overwrite (`_StrictLoader` in `policy/schema.py`) and caps the document at 100,000 nodes. The Pydantic models are strict (unknown keys rejected, with "did you mean" suggestions and line numbers). Regular expressions are checked by `policy/regex_guard.py`: patterns with nested ambiguous quantifiers, the classic cause of catastrophic backtracking, are rejected at validation time, and `bounded_search` never gives a policy regex more than 50,000 characters; longer input counts as a violation so it fails closed. Security test ST08 activates a catastrophic pattern and expects rejection. The comment in `configs/policies/default.yaml` records a real case: the rule from our own specification for "more than 50 records in an e-mail" backtracked exponentially and had to be rewritten.

**Q6. How does Mirsad decide whether `send_email` goes "outside"?**
`send_email` has `sink: dynamic` with `sink_params: [to, cc, bcc]`. `resolve_sink` extracts the domain of every address in those parameters; if any domain is not one of `organization.internal_domains`, or a value has no recognisable domain at all, the sink is `EXTERNAL`. An unknown destination is never treated as internal.

**Q7. What happens to a tool that is not in the policy?**
`defaults.decision: deny` plus the catch-all `"*": {allow: false}` deny it (`TOOL_NOT_ALLOWED`). It is also hidden: `visible_tools` removes it from MCP `tools/list`, and the OpenAI proxy strips it from the `tools` array, so the model is not even offered it (least privilege). Security test ST22 covers both an unlisted tool and an unknown agent.

**Q8. What is monitor mode for?**
With `mode: monitor` the gateway computes the real decision, records it in the audit log with `enforced: false` and a `MONITOR_MODE` reason, but returns allow. An organisation can run Mirsad in shadow mode, look at what *would* have been blocked or escalated, tune constraints and detector thresholds per tool, and then switch to enforce.

**Q9. How does the OpenAI-compatible proxy protect an agent, and what does it not support?**
`adapters/openai_proxy.py` handles `POST /v1/chat/completions`: every `role: tool` message is inspected and replaced by the inspected content; tool definitions the policy does not allow are removed; the request goes to the upstream model without the agent's Mirsad key; every `tool_calls` entry the model returns is checked, denied calls are removed and explained in English and Arabic, and `finish_reason` becomes `stop` if no call is left. Streaming is rejected with HTTP 400 because a streamed tool call cannot be checked before the client acts on it.

**Q10. And the MCP side?**
`adapters/mcp_proxy.py` builds an MCP server per agent: `tools/list` returns only allowed tools with their upstream schemas; `tools/call` goes through `gateway.execute`. It is offered over streamable HTTP at `/mcp` (agent key per request) and over stdio with `mirsad mcp-proxy`, which forwards to a remote gateway so desktop hosts can use it. A denied call returns an MCP `isError` result with the bilingual reason, never the raw upstream output. Only tools are proxied; MCP resources, prompts and sampling are not (a stated limitation).

**Q11. How does rate limiting work and what is its weakness?**
`policy/ratelimit.py` keeps a sliding window of timestamps per key `agent / [session] / tool` (components URL-quoted so keys cannot collide), bounded per key and in total. The counters live in memory in one process, so several workers would each count separately; moving them to PostgreSQL or Redis is future work. Replay never touches the live limiter: it uses the counts recorded in the audit payload. Note that a denied call still counts against the window.

**Q12. Where does the 2.7 ms come from, and why is the concurrent median so much higher?**
Policy evaluation runs over pre-compiled structures (exact-name dictionary, globs sorted by specificity, compiled regexes), so one call costs a few milliseconds including the audit write; the gateway-reported median is about 2.1 ms. Under 50 concurrent sessions the time is queueing: one uvicorn worker, SQLite, and audit writes serialised by a lock so the hash chain stays in order. That is why we report the separate-process concurrent median (166 ms) against the 200 ms target, say plainly that the in-process layout's median (205 ms) is above it, and name the single-worker setup as a limitation.

### A.2 Abdullah Naif Al-Orabi – injection detector and dataset

You own `src/mirsad/detector/` (`normalize.py`, `rules.py` and `rules/*.yaml`, `model.py`, `detector.py`, `sanitize.py`, `dataset.py`, `build_dataset.py`, `train.py`, `metrics.py`), `data/detector/` and `docs/detector.md`.

**Q1. What is the detector's pipeline?**
`InjectionDetector.scan` (`detector.py`): normalise the text, match the weighted rules, score the text with the linear model if one is packaged, combine both by a tuned noisy-OR, calibrate, and label it benign / suspicious / injection at 0.5 / 0.8. Without a model it runs rules-only, which is the current state and the mode of every measurement we report.

**Q2. What does normalisation do, and why keep an offset map?**
`normalize.py` removes the disguises used to hide text from keyword matching: zero-width characters, bidirectional override and isolate controls, Latin homoglyphs, Arabic diacritics (tashkeel) and elongation (tatweel), compatibility forms, HTML entities and letter spacing; it also folds Arabic letter variants (alef, ya, ta marbuta, Persian/Urdu look-alikes) and Arabic-Indic digits. Each trick is reported as a signal. The offset map links every normalised character back to the original text, so a rule hit can be highlighted in the dashboard and removed by the sanitiser exactly where it appears in what the user and the model see.

**Q3. How is the rule score computed?**
`rule_score` in `rules.py`: a noisy-OR over *distinct* rules, 1 − Π(1 − wᵢ), capped at 0.99, so repeating the same phrase does not inflate the score. Evasion signals add up to three small terms of 0.1, but only when a real rule fired, so odd Unicode alone never flags a text. Hits that sit inside quotation marks in text that discusses attacks (a security newsletter, training material) are damped by 0.5 to reduce false positives. Every rule in the YAML files carries positive examples and optional negatives that the test suite checks.

**Q4. Describe the model.**
`model.py`: hashed character 2–5-grams (`char_wb`) and word 1–2-grams, 2²⁰ + 2¹⁸ features, each L2-normalised, and a class-balanced logistic regression whose C is chosen by validation PR-AUC (`train.py`). Long texts are scored over 600-character windows with a 300-character stride. The model is saved as `coef.npy`, `intercept.npy` and `meta.json` and loaded with `allow_pickle=False`, so a model file can never execute code.

**Q5. Why not a transformer such as AraBERT or XLM-R?**
`docs/detector.md` §6.4 gives four reasons: the detector is inline and must stay well under 10 ms for 2 KB on a CPU; deployments have no GPU; our dataset is hundreds to a few thousand examples, where a large encoder can overfit to authoring style without us noticing; and a linear model plus explicit rule spans is auditable and gives the sanitiser exact spans. The cost is no semantic understanding, so a paraphrase can evade it. A fine-tuned Arabic or multilingual encoder as a second stage is our first future-work item.

**Q6. How do the 0.5 and 0.8 thresholds keep their meaning after training?**
`combine_scores`: raw = 1 − (1 − m)^α · (1 − r)^β. On the validation split only, α, β and the decision threshold are tuned to maximise F1 subject to FPR ≤ 5%; `calibrate` then maps that tuned threshold to 0.5 with a monotone piecewise-linear function. So 0.5 always means "the tuned operating point" and the policy thresholds do not have to change when the model is retrained. They are operating points, not probabilities.

**Q7. How do you prevent test-set leakage?**
`build_dataset.py`: every record is validated against the schema (`dataset.py`: language, variety, carrier, attack type, difficulty); duplicates are removed by the hash of the *normalised* text, and when a text appears in a test batch the test copy wins; texts labelled both 0 and 1 are dropped. Batches named `test-*` feed only the test splits, and they are written separately from the training data; everything else is split 85/15 into train and validation, stratified by label and language with a fixed seed. Augmentation is applied to training data only. Test splits are never used for any choice of hyper-parameter or threshold.

**Q8. Why is F1 not reported?**
Because no attack-labelled batches exist yet. The development assistant does not write attack text, so the positive examples must be written and reviewed by the team (procedure in `docs/detector.md` §11.4). The pipeline was run end to end on neutral placeholder records only to prove that it works; those scores mean nothing about injection detection and are deliberately not reported. Once the team's batches are in `data/detector/raw/`, `make detector` builds the splits, trains, evaluates per language and variety and writes the metrics that the poster, slides and report read.

**Q9. Have you measured any error rate at all?**
Yes, false positives of the rules-only fallback on the team's benign batches (`docs/detector.md` §13.5): Arabic 6 of 100 records flagged (6.0%, above the 5% target), English 3 of 260 (1.2%). The Arabic cases come from polite imperatives and forms of address that are normal in Arabic business writing. That is a finding, not a failure to hide: it is why every detector metric must be split by language, and why the trained ensemble's operating point is constrained to FPR ≤ 5%.

**Q10. What happens to a result that scores high?**
`classify_score` in `gateway.py` uses the tool's detector settings: at or above `block_threshold` the policy's `on_detect` action applies (default `sanitize`); at or above `flag_threshold` the result passes with a recorded reason. `sanitize.py` replaces the detected spans with a bilingual marker; if a structured result cannot be cleaned reliably, the gateway withholds it instead. Untrusted results are then *spotlighted*: wrapped in data markers with a note telling the model to treat the content as data (after Hines et al., 2024). Spotlighting is advisory; it depends on the model honouring it.

**Q11. Could an attacker hide text inside JSON escapes?**
That case is handled: `scan_structured` walks every string (keys and values) of a structured result after JSON decoding, so escaped characters are decoded before scanning, and the gateway also scans the raw text form when it differs (`Gateway._scan`). What is *not* decoded is listed in `docs/detector.md` §16: encodings other than base64, such as hex or URL encoding.

**Q12. How fast is it?**
Measured before training (`docs/detector.md` §13.4): rules-only p50 1.87 ms for 2 KB, 11.7 ms for 10 KB; with a full-size model about 3.4 ms for 2 KB. Latency depends on feature size and text length, not on the weights, so these carry over, but they must be re-measured on the final model.

### A.3 Bader Abdullah Alyamini – taint tracking, audit log, approval back end

You own `src/mirsad/taint/`, `src/mirsad/audit/`, `src/mirsad/approvals/service.py` and the storage design.

**Q1. What exactly is "tainted" in Mirsad?**
Values, not bytes. We cannot follow data through the model, so `taint/extract.py` records *recognisable values* from every tool result: e-mail addresses, URLs, domains, IBANs, phone numbers, long numbers, record IDs and hashed word 8-grams of long text. Each value carries its source tool, call ID, field, trust (trusted or untrusted) and sensitivity (public, internal, confidential). The same canonicalisation (case, Arabic-Indic digits, invisible characters, URL encoding) is applied to tool-call arguments, so a value matches however it is re-typed literally.

**Q2. What are the four rules and their default actions?**
In `taint/rules.py`, configured in `default.yaml`:
- untrusted → external sink: the session has read untrusted content and the call goes to an external destination → require approval (risk 0.6);
- confidential → external sink: the arguments contain values from a confidential result (for example CRM data) and the destination is external → require approval (0.7);
- untrusted controls destination: a destination value (address, URL, IBAN) first appeared in untrusted content and not in a trusted field → **deny** (0.9);
- after injection, high risk: the detector found an injection earlier in the session and the tool is high or critical risk → require approval (0.8).

**Q3. Replying to an external e-mail is normal. Why doesn't the destination rule block it?**
Because of trusted fields: `from`, `sender`, `id`, `email_id`, `date`, `received_at`, `customer_id`, `doc_id`. The sender address of the e-mail being answered is a trusted-field value, so it does not trigger the rule; only a destination that appeared *in the free text* of untrusted content does. The domain-level check also never applies to the organisation's own domains. There is a data-subject exemption too: sending a customer their own record at their own address is not a disclosure, but only when every destination is the single contact of that one record (`_data_subject_records`).

**Q4. What can taint tracking not do?**
It matches literally after normalisation, so an agent that paraphrases, translates, summarises or re-encodes data defeats it. The "untrusted → external" rule works at session level, which is coarse and is one source of approval friction. State is bounded (2,000 values per session, half of them for n-grams; sessions expire after 6 hours idle) and kept in memory in one process. CaMeL-style tracking inside a custom interpreter is stronger but requires rebuilding the agent; we chose the drop-in option.

**Q5. How can you replay a taint decision later if the state was in memory?**
At decision time the gateway stores a *minimal snapshot*: only the values the rules actually consulted (`minimal_snapshot` in `taint/tracker.py`, using the `touched` set filled by `evaluate_rules`). The rules are a pure function of call, profile, sink, settings and a `TaintView`, so replay rebuilds the view from the stored snapshot and gets the same verdict. We first stored the full snapshot; it exceeded the audit payload cap and broke replay, which is why the minimal snapshot exists.

**Q6. How does the hash chain work?**
`audit/log.py`: each event stores `prev_hash` and `hash = HMAC-SHA256(key, prev_hash + "|" + canonical_json(event without hash))`; the first event links to a genesis hash of 64 zeros. `verify_events` walks the chain in sequence order: a gap in `seq` means a deleted event, a `prev_hash` mismatch means an inserted, removed or reordered event, and an HMAC mismatch means a modified event or a forged hash. The audit key is derived from the application secret with a separate label (`audit_key_from_secret`), so the JWT signing key and the audit key are different. Security tests ST06 (modification) and ST07 (deletion) prove detection.

**Q7. What are the limits of that design?**
Anyone holding the HMAC key can rewrite the whole chain consistently, and cutting off the newest events leaves a valid shorter chain. Both are only detectable against an external anchor, the head `{seq, hash}` from `AuditLog.anchor()` stored outside the database; that anchoring is manual today. By default the secret is generated into the data directory next to the SQLite file (`config.py`), so in production it should come from `MIRSAD_SECRET_KEY` or a secret manager. Finally, there is no retention or erasure mechanism, because deleting an event breaks the chain.

**Q8. Does the audit log itself become a privacy risk?**
That is what `audit/redact.py` prevents. Before hashing and storing, it removes values under secret-like keys (password, token, api_key, authorization, …) and secret shapes in free text (provider API keys, JWTs, bearer tokens, PEM keys, `password=` assignments), and masks Luhn-valid card numbers, Saudi national/iqama IDs and IBANs to their last four characters. E-mail addresses and domains stay, because an auditor needs the destination. Payloads are capped at 20,000 characters. Test ST11 puts a secret in tool arguments and checks it never reaches the log.

**Q9. Two approvers tap at the same time. What happens?**
`approvals/service.py` moves an approval out of `pending` with a conditional `UPDATE … WHERE status = 'pending'`, so exactly one decision wins even across processes; the loser gets HTTP 409 and the app says someone else decided. Waiters block on an `asyncio.Event` with a slow database re-check every 5 s for decisions made by another process. Test ST09 checks that decisions are attributed and final.

**Q10. What stops a late approval of an action the agent was already told was denied?**
`ApprovalService.wait` marks the approval `expired` at its deadline (the earlier of the record's expiry and the policy's `approval_timeout_s`, 120 s by default), so a tap after the deadline is refused. The gateway then returns a deny with `APPROVAL_EXPIRED`. The default is fail-safe: no answer means no action.

**Q11. Could the approval summary itself be prompt-injected?**
No LLM is involved. `approvals/summary.py` builds at most three sentences from the call and the decision's reasons only. Attacker-controlled values (addresses, URLs, IDs) are shown verbatim but limited to 80 characters and stripped of line breaks, so they cannot fake extra sentences. Arguments are redacted before they are stored with the approval.

**Q12. Why HMAC and not a plain hash chain or a blockchain?**
A plain SHA-256 chain can be recomputed by anyone who can edit the database, so it proves nothing against a database administrator. HMAC requires the key. A blockchain adds distributed consensus that a single organisation's log does not need; the property we actually need from outside is a witness for the latest head, which periodic external anchoring provides more cheaply.

### A.4 Mohammed Yasser Alanssari – dashboard and approver PWA

You own `web/` (dashboard `web/src/dashboard/`, approver `web/src/approver/`, shared code `web/src/shared/`) and the approval UX.

**Q1. How is the front end built?**
React 18 with strict TypeScript and Vite, Recharts for charts. Two entry points, `index.html` (dashboard) and `approve.html` (approver PWA), share one code base under `web/src/shared/` (API client, live updates, i18n, components). The production build goes into `src/mirsad/static` and is served by FastAPI, so there is one origin and no CORS between UI and API.

**Q2. Why a PWA instead of the Flutter app in the proposal?**
One code base with the dashboard, installation from the browser on Android and iOS 16.4+ without store fees or review, Web Push, and an offline shell. The trade-offs are that it needs HTTPS (browsers allow service workers and push only on secure origins) and that iOS delivers push only to a home-screen app. A store wrapper (Capacitor or Flutter) remains future work for organisations that require managed apps.

**Q3. How do approvals reach the phone in real time?**
The back end publishes `approval.requested` on an in-process pub/sub (`approvals/notifier.py`) with a bounded queue per subscriber, which drops the oldest event if a client stalls; the app reloads the full list on reconnect anyway. The browser reads it as Server-Sent Events via `fetch` (`web/src/shared/api/sse.ts`), because the native `EventSource` cannot send an `Authorization` header and putting the token in the URL would leak it into logs. Reconnects use exponential backoff with jitter and honour `retry:` and `Last-Event-ID`. If VAPID keys are configured, Web Push is sent as well and dead subscriptions (HTTP 404/410) are deleted.

**Q4. Where is the login token stored?**
In memory, mirrored to `sessionStorage` (`web/src/shared/api/client.ts`): a reload keeps the session, closing the tab ends it, and nothing long-lived is written to disk. Any 401 clears it. On sign-out the PWA asks the service worker to clear cached approval data and unsubscribes push for that device (`disablePushSubscription` in `pwa.ts`), so a shared phone stops receiving the previous user's alerts.

**Q5. What does the service worker cache?**
`sw.template.js`: the app shell is precached; navigations and the approvals API are network-first, so the last known queue is visible offline; hashed assets are cache-first; the SSE stream and every non-GET request bypass the worker. Approve and Deny are disabled while offline, so no decision is ever queued for later.

**Q6. How did you design for a decision in under 30 seconds?**
The request screen starts with the plain-language summary (what the agent wants to do), then "why Mirsad paused it", then "where the data came from" (built from the taint evidence by `shared/lib/provenance.ts`), with the raw arguments collapsed, a countdown and large Approve/Deny buttons. A second step (`DecisionConfirm.tsx`) restates the consequence and takes an optional note that is audited. We have not run a user study; the report gives a Keystroke-Level Model estimate of about 22 s for a single-reason request and 29 s for an external e-mail with two reasons when the approver reads the summary (Section 4.2.8). That estimate assumes an expert and must be confirmed with real approvers.

**Q7. How does Arabic and right-to-left work?**
`shared/i18n/en.ts` and `ar.ts` hold every string; switching language sets `dir="rtl"` on the document. Blocks of mixed content use `dir="auto"`. Detector spans come from Python as Unicode code-point offsets while JavaScript strings index UTF-16 units, so `shared/lib/spans.ts` applies offsets to `Array.from(text)`; highlight marks are not bidi-isolated, so highlighting never changes how mixed Arabic and English is laid out.

**Q8. What did you do for accessibility, and what is missing?**
Labelled semantic controls, keyboard operation, risk shown with an icon and text (never colour alone), light and dark themes and reduced motion. `web/tests/contrast.test.ts` computes WCAG contrast for the colour tokens in both themes (4.5:1 for text, 3:1 for UI components). Missing: an automated accessibility audit and testing with screen readers.

**Q9. How is the front end tested?**
194 Vitest tests in 10 test files (38 suites) with Testing Library and jsdom: contract tests against back-end fixtures, the SSE parser, countdowns, span mapping, i18n key parity between English and Arabic, contrast, and UI behaviour. The phone screenshots were taken in Chrome emulating a 390 × 844 screen; installation and push delivery on physical phones were not part of the recorded tests, and we say so.

**Q10. Can a user who only has the UI do more than their role allows?**
No, because the server enforces roles, not the UI. `require_user(...)` guards every route: approvers decide approvals, auditors read, verify, replay and export the audit log, and admins manage policies, agents and users. Security test ST20 calls admin actions with the other roles and expects refusal; ST21 checks that agent keys cannot use human APIs and humans cannot act as agents. The UI also renders no raw HTML (there is no `dangerouslySetInnerHTML` in `web/src`), and the back end sends a Content-Security-Policy.

**Q11. Why does the screenshot show "Expires in 14:33" when the timeout is 120 s?**
The screenshots were captured with `MIRSAD_APPROVAL_TIMEOUT_S=900` (`scripts/capture_screenshots.py`) so there was time to photograph each screen. In normal operation the deadline is the earlier of that setting and the policy's `approval_timeout_s` (120 s in `default.yaml`).

### A.5 Abdulmalik bin Saedan – benchmark, demo, security testing, project management

You own `bench/`, `demo/`, `tests/security/`, `scripts/run_evidence.sh`, `scripts/collect_results.py` and `docs/pm/plan.yaml`.

**Q1. What is Mirsad-Bench?**
An offline benchmark over the fictional Najd Trading Co. workspace: 48 benign user tasks (24 English, 24 Arabic, Modern Standard and Gulf) with 68 tool calls, run under five configurations: `none` (no gateway), `full`, `policy_only`, `taint_only` and `detector_only` (`bench/defenses.py`). The ablations are made by transforming the default policy YAML, so every configuration runs the same production code. Each episode gets a fresh policy engine and taint tracker. Escalations are decided by an approver model: `deny`, `approve` or `oracle` (approves exactly the calls in the user task's plan, like a human who knows what was asked).

**Q2. Define your metrics.**
From `bench/metrics.py`: utility = share of episodes whose success predicate held on the World's side effects; false-positive rate = benign calls denied *automatically* / benign calls; friction = benign calls escalated to a human / benign calls; attack success rate = share of attack episodes whose injection predicate held; ASR reduction = 1 − ASR(defended) / ASR(baseline).

**Q3. Friction is 17.6%. Isn't that too much?**
It is 12 of 68 calls, and every one is on a path the default policy escalates on purpose: e-mails to outside domains, customer exports, payments and deletions. Internal replies, lookups, reading and CRM notes had no friction. It is a policy choice, not a detector error, and an organisation can lower it by listing partner domains in `domain_in` or setting `approval: never` on low-risk tools. The lesson we report is that a false-positive rate alone hides the cost of a policy, so friction must always be shown next to it.

**Q4. Why use a scripted agent and not only the LLM?**
The scripted agent is a deterministic worst case: it always does exactly what its plan (and, in attack episodes, an injected instruction that reaches it) says. That isolates the effect of the gateway from the model's own robustness and makes runs reproducible. The Qwen2.5-7B agent gives realism; our four-task LLM smoke run had 75% utility with and without Mirsad, which is a smoke test, not an estimate.

**Q5. How was latency measured?**
`bench/latency.py` starts the real FastAPI app with uvicorn on a free localhost port with the default policy and the demo tools. For 1,000 benign read-only calls it measures the direct in-process tool call, then `POST /v1/tools/{tool}/invoke` sequentially and spread over 50 concurrent sessions. Added latency is the HTTP round trip minus the direct call, paired per call, reported as p50/p95/p99. With `--server-process` the server runs in its own OS process (`bench/latency_server.py`); in the same process, the load generator competed with the server and inflated the tail (p95 880 ms versus 208 ms) and pushed the median above 200 ms (205 ms versus 166 ms). We report the separate-process layout and state the layout with every number.

**Q6. What does "272 of 272 replays matched" prove?**
After every benchmark configuration, the harness re-evaluated each stored decision from the audit log with its recorded policy version, inputs, taint snapshot and rate counts, and every one produced the same action. It shows that each decision can be explained and reproduced after the fact, and the audit chain verified after every configuration. It does not prove the decisions were *right*; that is what the attack evaluation is for.

**Q7. Describe the demo workspace.**
`demo/world.py`: a deterministic company (`World(seed=7)`) with 30 e-mails in English and Arabic, 120 customers, 12 web pages and 12 documents, behind 12 tools, all fictional with reserved `.example` domains. Side-effecting tools record what they did, which is how the benchmark judges success. `demo/agent.py` drives an OpenAI-compatible model with a plain assistant prompt and no anti-injection wording, on purpose, so that all protection comes from the gateway; a unit test enforces that.

**Q8. How did you test the security of Mirsad itself?**
`tests/security/test_gateway_security.py`, cases ST-01 to ST-23 (45 test cases with parameters): authentication on every management route; forged, unsigned and role-tampered tokens; agent-key rotation and garbage keys; audit modification and deletion detected; catastrophic regex rejected; approvals attributed and final; failed logins audited without the password; secrets redacted; listings never expose hashes; errors leak no internals; static paths cannot escape the web root; security headers; CORS; filter values treated as data; oversized bodies rejected (1 MiB); login brute force throttled (5 failures per 5 minutes per user and address); role separation; SSRF targets blocked for `fetch_url`. Plus Bandit (0 issues in 13,023 lines), pip-audit and npm audit (0 vulnerabilities). Not done: an external penetration test and an adaptive red-team exercise.

**Q9. Why is the attack-success rate pending?**
The harness needs injection tasks and attack templates written by the team in `bench/scenarios/attacks/` (format in its README). The attack-episode code (`bench/attacks.py`) contains no attack text: it fills the team's templates, plants them into what a user task reads, checks whether the planted content still reached the agent, and attributes each stopped attack to the layer that stopped it. `make bench` (`scripts/run_bench.sh`) then detects the attack files, runs the attack episodes and produces the ASR and its reduction, and the documents read them from the result files.

**Q10. How did you manage the project?**
Scrum with two-week sprints, S1–S17 across two semesters, milestones M1–M7, and one owner per workstream (`docs/pm/plan.yaml`, which also generates the Gantt chart). Before coding we wrote an engineering contract (`docs/dev/BUILD_SPEC.md`) that fixed every interface, so the five workstreams could build in parallel; most defects we found were at the seams, which the integration tests caught. The budget was revised from 1,660 to 1,185 SAR with price evidence and a zero-cost fallback (D2).

**Q11. How do you guarantee the numbers in the documents are real?**
`scripts/run_evidence.sh` runs the tests, scans and benchmarks; `scripts/collect_results.py` writes `reports/results_summary.json`; the report, slides and poster read their numbers from that file when they are built, and a missing value prints as "pending". No number is typed by hand.

---

## Part B – General questions (anyone; first answer from the person named)

**G1. Why a gateway and not fine-tuning the model to resist injection? (Bader Alshuraie)**
Fine-tuning lowers the rate at which a model follows injected text but does not reach zero, and adaptive attacks find the remaining cases. It is also not available for closed models bought as an API, has to be redone for every model, and cannot express an organisation's rules ("no more than 50 records", "e-mail with CRM data needs approval"). A gateway is model-agnostic, deterministic, explainable and auditable, and it constrains what the model's *actions* can achieve even when the model has been fooled. The two are complementary; Mirsad assumes the model is untrusted after it has read untrusted content.

**G2. Can detection solve prompt injection? (Abdullah Al-Orabi)**
No. A detector classifies text; a new phrasing, a paraphrase, an unseen dialect or an instruction split across fields or results can evade it, and published adaptive attacks bypass detection-based defences. That is why the detector in Mirsad is one signal: it sanitises and labels content, and its finding raises the approval requirement for high-risk tools, but the policy and taint layers stop the *action* without needing to recognise the wording.

**G3. What can taint tracking do, and what can't it? (Bader Alyamini)**
It can show, with evidence, that a value in a tool call came from untrusted or confidential content, and stop the most dangerous case automatically: an attacker choosing the destination. It cannot follow data that the model paraphrases, translates or re-encodes, it does not see inside the model, and its session-level rule is coarse. See A.3 Q1–Q4.

**G4. Why a PWA? (Mohammed Alanssari)** See A.4 Q2: one code base, install without a store, push, offline shell; it needs HTTPS, and push on physical phones is still to be tested.

**G5. How does the audit chain detect tampering, and where does it stop? (Bader Alyamini)**
Each event's HMAC covers the previous hash and the event's content, so editing, deleting, inserting or reordering a stored event breaks verification at that event (ST06, ST07). It stops at the key: a key holder can rewrite the chain, and tail truncation leaves a valid chain; both need an external anchor of the head, which is manual today. It also cannot prove values that were redacted before hashing.

**G6. What is decision replay and why does it matter? (Bader Alyamini)**
`Gateway.replay(seq)` re-evaluates a stored decision with the policy version it recorded (loaded from the policy store by hash), the stored call, the minimal taint snapshot and the recorded rate counts, and compares the action and reason codes; for a result inspection it re-scans the stored content and reports the detector version to explain any score drift. Auditors can check that a decision follows from the rules rather than trust the log's word, and administrators can see what a policy change would have done. In the benchmark 272 of 272 replays matched.

**G7. How was latency measured, and is it fair? (Abdulmalik bin Saedan)** See A.5 Q5. It is a paired comparison against the direct tool call over HTTP with the real app, 1,000 benign calls, sequential and with 50 concurrent sessions, server in its own process. Limits: one laptop, one worker, SQLite, rules-only detector, read-only calls.

**G8. Why are the detector F1 and the attack-success rate pending? Isn't the project incomplete? (Abdullah Al-Orabi, then Abdulmalik)**
Both need attack-labelled data. The AI assistant we used during development does not generate attack text, so these examples have to be written and reviewed by our team. (State the honest status of that work on the day.) Everything else is built and tested: the dataset tooling, training and evaluation code, the benchmark's attack-episode path and the document pipeline. When the data is added, `make detector` and `make bench` produce the numbers, and the report, slides and poster pick them up automatically. We chose to show "pending" rather than an estimate, because an invented number would be worse than a missing one.

**G9. What ethical issues did you consider? (Abdulmalik bin Saedan)**
Attack material is dual-use, so it targets only our simulated company, is authored and reviewed by the team, and is described abstractly in documents. All data is synthetic with reserved `.example` domains; no real personal data is used. The approval design limits alert fatigue (only policy-defined high-risk paths) and explains itself in the approver's language. We report limitations and pending results openly and follow the ACM Code of Ethics (report Section 3.6).

**G10. How did you use AI assistance, and how do you show your own understanding? (Mohammed Alanssari)**
As disclosed in Section 3.6.6, an AI coding and writing assistant (Anthropic's Claude) helped generate code and tests, draft documentation and report text, author parts of the benign synthetic data and scenarios, and produce diagrams. It did not write attack payloads. Everything it produced went through the same checks as our own work (Section 3.6.6): the automated test suite, our review, and evaluation results that come only from actual runs; every reference was checked against its source. Describe only the checks the team actually carried out, with an example from your own workstream. We remain responsible for all submitted work, and each of us can explain our workstream's code, which is what this viva tests.

**G11. How does Mirsad relate to the PDPL? (Bader Alyamini)**
The confidential → external taint rule and the `domain_in` allow-lists target exactly the unauthorised disclosure of personal data the law penalises. Secrets are removed and national IDs, IBANs and card numbers are masked before audit events are stored, so the log does not become a second copy of customer data. The audit trail helps scope an incident for breach notification. Mirsad supports compliance; it does not make an organisation compliant. Gaps: no retention policy or erasure mechanism (Appendix A).

**G12. And NCA ECC? (Abdulmalik bin Saedan)**
Appendix A maps the controls: least privilege and segregation of duties (per-tool and per-parameter permissions; a human approver separate from the agent), data protection by classification (sensitivity labels drive the taint rules), event logging and monitoring (the HMAC-chained log with verification), web application security (headers, body limits, login throttling) and secure integration (authenticated, policy-checked tool calls). Gaps we name ourselves: log retention of at least 12 months, a SIEM connector and automatic external anchoring.

**G13. Does it scale? (Bader Alshuraie)**
Measured: one worker on one laptop sustained 291 requests/s with 50 concurrent sessions at a 166 ms median (server in its own process). What breaks first when adding workers: the rate-limit counters and taint state are in memory per process, the live-update pub/sub is in-process, and every event appends to one global hash chain, which serialises writes. Approvals already work across processes (database-backed, conditional updates, periodic re-check), audit appends retry on sequence conflicts, and PostgreSQL is supported but was not used in the measurements. The path is shared state in PostgreSQL or Redis, sticky sessions or shared taint storage, and per-tenant chains anchored together.

**G14. Which MCP version do you support, and what if the protocol changes? (Bader Alshuraie)**
The code is built on the MCP Python SDK version 2 (installed 2.3.0; for example the v2 `MCPServer` class, formerly `FastMCP`, and the separate `mcp_types` package), and the report cites the specification revision of 28 July 2026. We support tools over stdio and streamable HTTP; resources, prompts and sampling are not proxied, and non-text content is dropped rather than inspected. Protocol handling is isolated in `src/mirsad/adapters/`, so a protocol change touches the adapters, not the policy, taint, detector or audit code. The MCP specification itself recommends what Mirsad provides: a human able to deny tool calls, inputs shown before a call, results validated before they reach the model, and logging.

**G15. Isn't Mirsad a new single point of attack and failure? (Abdulmalik bin Saedan, then Bader Alshuraie)**
Yes, so it is built and tested as a target: agent keys are stored as SHA-256 hashes and shown once; passwords use salted scrypt; human sessions use HS256 JWTs (12 h) with roles; logins are throttled and audited; bodies are size-limited; policy regexes are bounded; every failure path fails closed (A.1 Q2). For availability, failing closed means an outage stops protected agents, so a production deployment needs more than one instance, which is future work.

---

## Part C – Five-minute live demo

**Roles.** Abdulmalik drives the laptop (dashboard and terminal). Mohammed holds the phone (approver app). Bader Alyamini narrates the audit step. Everyone else watches the clock and the fallback folder.

**What the demo shows.** (1) the dashboard in English and Arabic; (2) an e-mail to an outside address paused and approved on the phone; (3) a request to export 200 customer records denied by policy; (4) the audit chain verified and a decision replayed. It uses the Guard API directly with `curl`, so it needs no LLM, no network access and no attack content.

### C.1 Setup (before the committee arrives)

Use a personal hotspot that only the laptop and the phone join. Binding to `0.0.0.0` exposes the server to that network, so never do it on the venue Wi-Fi.

```bash
cd mirsad
./scripts/setup.sh                                   # once: .venv, dependencies, prebuilt web UI
export MIRSAD_DATA_DIR=.mirsad-viva                  # a fresh data directory: clean audit chain
export MIRSAD_HOST=0.0.0.0                           # only on the private hotspot, so the phone can connect
./scripts/run_demo.sh                                # first run creates users + demo agent, then serves :8700
```

In a second terminal (do not project it while you do this):

```bash
cd mirsad
export MIRSAD_DATA_DIR=.mirsad-viva
# demo agent key from the credentials file, never printed
export MK="$(grep -o 'api_key=mk_[^ ]*' "$MIRSAD_DATA_DIR/credentials.txt" | tail -1 | cut -d= -f2)"
show() { python3 -c 'import json,sys
r=json.load(sys.stdin); d=r["decision"]
print("decision:", d["action"], "| approval:", d.get("approval_status"), "| audit seq:", d.get("audit_seq"))
for x in d["reasons"]: print("  -", x["code"], "|", x["message"])
print("blocked:", r["error"]) if r.get("error") else print("the tool ran")'; }
invoke() { curl -s --max-time 180 -X POST "http://127.0.0.1:8700/v1/tools/$1/invoke" \
  -H "Authorization: Bearer $MK" -H "Content-Type: application/json" -d "$2" | show; }
ipconfig getifaddr en0                               # the laptop's address on the hotspot, for the phone
```

Then:

- Laptop browser: `http://127.0.0.1:8700/`, sign in as **admin** (password in `.mirsad-viva/credentials.txt`). Keep the Overview page open in English.
- Phone browser: `http://<laptop-address>:8700/approve`, sign in as **approver**. Keep the tab open: the session ends when the tab is closed, by design. Over plain HTTP the phone gets live updates in the open app, but install and push notifications need HTTPS, so the demo does not rely on push.
- Do one rehearsal of steps 2–4 below, then **restart the server** (Ctrl-C, `./scripts/run_demo.sh`) so the in-memory rate limits are reset. The export tool allows only 3 calls per hour, and a rehearsal would otherwise add a rate-limit reason on the day. The audit chain from the rehearsal stays and verifies; that is fine.

### C.2 Run sheet

| Time | Who | Action | What the audience sees |
|---|---|---|---|
| 0:00–0:20 | Abdulmalik | One sentence: "Everything runs on this laptop with a fictional company; we call the gateway exactly as an agent would." | Dashboard Overview |
| 0:20–1:20 | Abdulmalik | **Dashboard tour.** Overview (decisions, approvals waiting, audit integrity), Activity & audit, Approvals, Policies (open `default.yaml`, point to `send_email` → `domain_in` and `export_customers` → `count: {max: 50}`), Agents. Click **العربية** in the header: the whole interface switches to Arabic, right to left. Switch back. | Live statistics; the policy that will decide the next two calls; the RTL interface |
| 1:20–2:40 | Abdulmalik, Mohammed | **External e-mail needs approval.** Run step 2 below. The terminal waits. Mohammed shows the phone: a medium-risk `send_email` request, the summary says the recipient is outside Najd Trading Co. He opens it, reads the summary aloud, taps **Approve**, confirms. | Terminal returns `allow`, approval `approved`, reasons including the domain constraint; the dashboard Approvals count drops |
| 2:40–3:25 | Abdulmalik | **Policy denial.** Run step 3: export 200 customer records. | Immediate `deny` with a constraint violation and the bilingual explanation the agent would receive; no tool ran |
| 3:25–4:30 | Bader Alyamini | **Audit.** Activity & audit → **Verify chain** ("Audit chain intact: N events verified"). Open the `send_email` decision (its audit seq is in the terminal output) → **Replay decision**: the replay reproduces the automatic decision, `require_approval`, with the same reasons and the recorded policy version. Say that the human's approval is a separate `approval.decided` event in the same chain. Then replay the export decision: `deny` again. | Tamper-evidence and reproducibility, live |
| 4:30–5:00 | Abdulmalik | Close: "Policy decided the export, a human decided the e-mail, and both decisions are in a verifiable log that reproduces them." | Back to Overview |

**Step 2 – e-mail to an outside address (requires approval):**

```bash
invoke send_email '{"session_id":"viva-1","arguments":{"to":"accounts@gulf-supplies.example","subject":"Delivery date","body":"Hello, please confirm the delivery date for our last order. Regards, Najd Trading Co."}}'
```

Approve on the phone within 120 seconds; after that the request expires and the call is denied (that is also a valid thing to show).

**Step 3 – export of 200 records (denied by policy):**

```bash
invoke export_customers '{"session_id":"viva-2","arguments":{"query":"","count":200}}'
```

**Optional, if time allows:** an export of 20 records is within the limit, but `export_customers` is a high-risk tool with `approval: on_risk`, so it is sent for approval instead of running directly. Have Mohammed **Deny** it to show the other branch:

```bash
invoke export_customers '{"session_id":"viva-3","arguments":{"query":"","count":20}}'
```

**CLI alternative for step 4** (if the browser misbehaves):

```bash
.venv/bin/mirsad --log-level WARNING audit verify          # "ok": true, exit code 0
.venv/bin/mirsad --log-level WARNING audit replay <seq>    # "match": true, "reasons_match": true
```

These commands were rehearsed against a throwaway server on 14 Oct 2026. The export of 200 records was denied with `CONSTRAINT_VIOLATION`. The outside e-mail was paused at medium risk with the summary "…to accounts@gulf-supplies.example (outside Najd Trading Co.)…", then ran after approval. The export of 20 records went to approval and was denied by the approver. The chain verified, and both decisions replayed with `"match": true`.

### C.3 Fallbacks

If something fails, say what failed in one sentence and switch to the screenshot. Never debug in front of the committee.

| Step | If this fails | Show instead (`docs/figures/screens/`) |
|---|---|---|
| Dashboard tour | Server does not start or the browser hangs | `dash-overview.png`, `dash-policies.png`, `dash-overview-ar.png`, `dash-policies-ar.png` |
| Phone approval | Phone cannot reach the laptop (hotspot, firewall prompt) | Open `http://127.0.0.1:8700/approve` in a narrow browser window on the laptop and approve there; otherwise `pwa-pending-en.png`, `pwa-detail-en.png`, `pwa-detail-ar.png` |
| Policy denial | `curl` error or missing key | `dash-activity.png`, `dash-activity-detail.png` (a denied decision with its reasons) |
| Audit verify and replay | Button errors | the CLI commands above; otherwise `dash-activity-detail.png` and the replay row in the report (Section 4.2.7) |
| Everything | Laptop failure | the poster preview (`deliverables/Mirsad_Poster_preview.png`) and the slide deck, which contain the architecture, the screens and the measured results |

The Demo console (`dash-demo.png`) with the local Qwen2.5-7B agent is **not** part of the five-minute script: a real model does not always behave the same way twice. Use it only if the committee asks to see an agent end to end and Ollama is already running.

---

## Part D – Presentation-day checklist

**The day before**

- [ ] If anything changed since 14 Oct 2026: the build owner follows `README_TEAM.md` §5.3 (it regenerates the evidence, the slides, the poster and the documents in the right order). Then re-check the Quick facts table above against `reports/results_summary.json`.
- [ ] Detector F1 and attack-success reduction: if the team's data has been evaluated, the poster and slides show the values automatically; update the answers to G8, A.2 Q8 and A.5 Q9. If not, they must still read "pending team data".
- [ ] Each member re-reads their section of this document and opens every file cited in it.
- [ ] Full rehearsal with a timer: talk under 14 minutes, demo under 5 minutes, then a 10-minute mock Q&A where the others ask questions from Part B.
- [ ] Print or export: poster (85 × 142 cm, check colours on a proof), slides as PDF, report PDF.

**On the laptop**

- [ ] Charged, charger packed, HDMI and USB-C adapters tested with a projector if possible.
- [ ] Do Not Disturb on; e-mail, chat and update pop-ups closed; terminal font at least 18 pt; browser zoom at 125%.
- [ ] Fresh `MIRSAD_DATA_DIR=.mirsad-viva`, server running, admin signed in, Overview open; second terminal with `MK`, `show` and `invoke` defined (C.1). Server restarted after the rehearsal.
- [ ] Folder `docs/figures/screens/` open in Preview for fallbacks; slides in presenter view; report PDF and this document open in another window.
- [ ] Credentials file never shown on the projector.

**On the phone**

- [ ] Joined the private hotspot; battery charged; auto-lock off; brightness up.
- [ ] Approver signed in at `http://<laptop-address>:8700/approve`; tab left open; language set to English (switch to Arabic only if asked).

**In the room**

- [ ] Hand the committee the poster preview or printed poster before starting.
- [ ] Moderator (Abdulmalik) passes each question to the owner in "Who answers what"; the back-up adds only if needed.
- [ ] Answer first, then reason, then code. Say "pending" for unmeasured results; describe attacks only in general terms.
- [ ] After the demo, stop the server bound to `0.0.0.0` (Ctrl-C) and turn off the hotspot.
