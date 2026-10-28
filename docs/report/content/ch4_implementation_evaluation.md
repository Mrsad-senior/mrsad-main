# Chapter 4 – Implementation and Evaluation

This chapter describes how Mirsad was built (Section 4.1), evaluates it against the success criteria fixed in the proposal (Section 4.2) and records how the work was divided (Section 4.3).

Every number in Section 4.2 is read from the result files under `reports/`, which `scripts/run_evidence.sh` regenerates (tests with coverage, security scans, latency benchmark, Mirsad-Bench and, when labelled data exists, detector training) before `scripts/collect_results.py` writes `reports/results_summary.json`. The values printed here were collected on {{reports/results_summary.json#generated_at}} (UTC); Appendix B.1 records the platform and when each part of the evidence was produced. Results that depend on attack-labelled data, which the team is still preparing, print as "[pending]" and fill in automatically once the result files exist.

## 4.1 Implementation

### 4.1.1 Development environment and repository structure

Mirsad was developed and measured on an Apple M5 laptop with 16 GB of memory running macOS 26.5 (arm64), Python 3.12 and Node.js 24. The demonstration agent and the LLM benchmark runs use Qwen2.5-7B [@qwen2024qwen25], served locally by Ollama through its OpenAI-compatible endpoint [@ollama-openai-compat]. Backend code is typed Python with Pydantic v2 models, linted with Ruff; the web front ends are strict TypeScript. A GitHub Actions workflow (`.github/workflows/ci.yml`) defines the continuous-integration checks: Ruff, the Python tests with coverage, Bandit, pip-audit, the TypeScript type check, the web tests, a production web build and a Docker image build. No CI run is recorded in `reports/`: the evidence in this chapter was produced locally with `scripts/run_evidence.sh` and, for Mirsad-Bench, `scripts/run_bench.sh` (Appendix B.1). These scripts run the tests, Bandit, pip-audit, npm audit and the benchmarks, but not Ruff, the TypeScript type check or the Docker build. Docker was not available on the build machine, so the `Dockerfile` and `docker-compose.yml` (gateway plus PostgreSQL 16) are written but have not been executed.

The code base contains {{reports/results_summary.json#code_size.python_src|,}} lines of Python in the `mirsad` package, {{reports/results_summary.json#code_size.python_demo_bench|,}} lines in the demonstration workspace and the benchmark, {{reports/results_summary.json#code_size.python_tests|,}} lines of Python tests and {{reports/results_summary.json#code_size.web_ts|,}} lines of TypeScript. @tab:i-repo lists the top-level folders.

Table: Top-level folders of the Mirsad repository {#tab:i-repo widths=1.2,4.8}
| Folder | Contents |
|---|---|
| `src/mirsad/` | Gateway package: `gateway.py`, `policy/`, `taint/`, `detector/`, `audit/`, `approvals/`, `storage/`, `auth.py`, `adapters/`, `sdk/`, `api/`, `cli.py` and `static/` (built web apps) |
| `web/` | React and TypeScript source of the dashboard, the approver PWA and their shared layer, with Vitest tests |
| `demo/` | Simulated Najd Trading Co. workspace, its MCP server, the demonstration agent and the Demo Console scenarios |
| `bench/` | Mirsad-Bench (loader, agents, defences, metrics, runner, reports) and the latency benchmark; `scenarios/` holds the user tasks |
| `configs/` | Policies (`default.yaml`, `monitor.yaml`, `strict-banking.yaml`) and upstream tool servers (`upstreams.yaml`) |
| `data/detector/` | Detector dataset: benign batches and generated splits; the team adds its attack-labelled batches here and public datasets under `data/detector/external/` |
| `tests/` | Python tests by area (adapters, api, audit, bench, demo, detector, integration, policy, security, taint) |
| `docs/` | Component documentation, the engineering contract (`dev/BUILD_SPEC.md`), diagrams, figures and report sources |
| `scripts/` | Setup, demo, benchmark and evidence scripts, screenshot capture and the report builder |
| `reports/` | Generated evidence: test results, coverage, security scans, benchmark runs and `results_summary.json` |

Each workstream implemented the public interfaces of the engineering contract (`BUILD_SPEC.md`, Section 3.4.1) and requested new dependencies through `docs/dev/deps-requests/` instead of editing shared files, which kept integration short and made the remaining seams visible (Section 4.1.13).

### 4.1.2 Gateway pipeline

The class `Gateway` in `mirsad/gateway.py` is the single enforcement point that every adapter calls. `check_call` decides on a tool call before it runs, `inspect_result` processes a tool result before the agent sees it, and `execute` chains the two around an executor supplied by the adapter.

`check_call` collects the reasons of the policy engine and then those of the taint tracker (using the sink the policy resolved) and combines them with a deny-overrides rule (`mirsad/models.py`): the most severe action wins and the risk score is the highest score of any reason.

```python
def combine_reasons(reasons: list[Reason]) -> tuple[Action, float]:
    """Deny-overrides combination: the most severe action wins; risk is the max score."""
    action = Action.ALLOW
    score = 0.0
    for r in reasons:
        if r.action.severity > action.severity:
            action = r.action
        score = max(score, r.risk_score)
    return action, score
```

If the combined action is ALLOW but the tool's approval setting asks for a human (`approval: always`, or `approval: on_risk` with a combined risk of at least 0.6 or a high-risk tool after a taint rule fired), the gateway adds an `APPROVAL_POLICY` reason and escalates. The decision is audited together with the call, the tool profile, the sink, every reason, a reduced taint snapshot, the rate-limit counters and the risk score, which are exactly the inputs needed to replay it (Section 4.1.6).

The pipeline fails closed: an exception in any layer yields a DENY with code `INTERNAL_ERROR`, and a call whose audit record cannot be written is denied with `AUDIT_UNAVAILABLE`, because an unrecorded action would violate NFR7. The synchronous evaluation runs in a worker thread under a lock, so concurrent sessions cannot interleave their updates to taint state and the audit chain. And when approval is required, `check_call` waits for a decision or the timeout, treats expiry as denial [@saltzer1975protection] and audits `approval.decided`; the reported latency excludes this human wait. In `mode: monitor` the decision is computed and audited with `enforced: false` but the call is allowed, for shadow deployment while a policy is tuned.

`inspect_result` treats results of unknown or disallowed tools as untrusted, truncates very large results (200,000 characters by default) and runs the detector when the profile asks for scanning. The score is mapped to pass, flag, sanitise or block with the thresholds of the tool's policy, and untrusted content that is not blocked is spotlighted: wrapped in data markers with a bilingual note telling the model to treat it as data [@hines2024spotlighting]. The original, unsanitised result is registered with the taint tracker so that provenance survives sanitising, and a `tool_result.inspection` event records the detection, the action and a SHA-256 digest of the content. `execute` also overwrites the call, session and agent identifiers on whatever the upstream returns, so an upstream cannot attribute its output to another call.

### 4.1.3 Policy engine

The policy language of Section 3.3 is implemented in `mirsad/policy/`. `schema.py` parses YAML into strict Pydantic models and reports errors with line numbers. `PolicyEngine` compiles a document once, splitting each agent's tool entries into exact names, globs ordered by specificity and a catch-all, and computes the version hash of Section 3.3.4 that every audit event names.

`evaluate_call` collects reasons in the fixed order of Section 3.3.4. The rate limiter is an in-memory sliding window per agent, tool and optionally session, with caps on timestamps per key and on keys, so a misbehaving agent cannot exhaust memory. In replay mode the engine uses the counts stored in the audit event and leaves the limiter untouched.

The sink decides whether the taint rules about external destinations apply. For tools declared `sink: dynamic`, such as `send_email`, it is computed from the destination arguments, and a destination without a recognisable domain counts as external:

```python
    def resolve_sink(self, call: ToolCall, profile: ToolProfile) -> SinkKind:
        """Static sinks as declared; ``dynamic`` by the domains of the destination arguments.

        A non-empty destination value with no recognisable e-mail/URL/host domain is
        treated as EXTERNAL: an unknown destination must not count as internal.
        """
        if profile.sink != "dynamic":
            return SinkKind(profile.sink)
        pieces = [piece for param in profile.sink_params for piece in iter_pieces(call.arguments.get(param))]
        if not pieces:
            return SinkKind.NONE
        internal = self.internal_domains()
        for piece in pieces:
            domains = piece_domains(piece)
            if not domains or any(not domain_matches(d, internal) for d in domains):
                return SinkKind.EXTERNAL
        return SinkKind.INTERNAL
```

Policy regular expressions run against arguments that a hijacked model may have produced, so a badly written pattern is a denial-of-service vector. `regex_guard.py` rejects patterns with nested ambiguous quantifiers at validation time and never passes more than 50,000 characters to a policy expression (for global rules, a longer argument counts as a match, so the check fails closed). Patterns are also applied to an NFKC-normalised copy with invisible characters removed, so full-width or zero-width variants of a blocked host name do not pass a `not_pattern` check. `Gateway.set_policy` swaps the engine atomically at run time, and every version is kept in the `policies` table so that old decisions can be replayed with the policy that made them.

### 4.1.4 Taint tracker

`mirsad/taint/` implements provenance tracking in the tradition of information-flow control and dynamic taint analysis [@denning1976lattice; @newsome2005dynamic], at the granularity a gateway can observe: values in tool results that reappear in later tool arguments. `register_result` extracts identifying values from structured and free-text results: e-mail addresses, URLs, domains, IBANs, phone numbers, long numbers, identifiers and, for confidential results only, BLAKE2b hashes of overlapping eight-word windows, so a copied passage can be recognised without storing it. Each value keeps its source tool, call, field, trust and sensitivity, and whether it came from a trusted field such as an e-mail's sender. A session keeps at most 2,000 values (n-gram hashes may use half, so a long document cannot push identifiers out) and is discarded after six idle hours.

`evaluate_call` in `mirsad/taint/rules.py` implements the four rules of @tab:d-taint as one pure function of the call, profile, sink, settings and a view of the session state, and the same function serves live evaluation and replay. The evidence of each taint reason names the source tool, call and field, which the approver sees as "where the data came from".

Integration exposed two details. The tracker needs the organisation's internal domains, which belong to the active policy and can change at run time, so `mirsad/api/components.py` gives the tracker a function that reads the domains from the gateway's active policy instead of a fixed list. The second detail concerns replay: a full session snapshot can exceed the 20,000-character limit on audit payloads, and a truncated snapshot no longer reproduces the decision. `minimal_snapshot` therefore stores the session flags and only the values the rules consulted for the call.

### 4.1.5 Injection detector

The detector in `mirsad/detector/` implements the six stages of Section 3.3.6. `normalize()` keeps a map from each normalised character to its original position, so spans found in the normalised text can be highlighted and removed in the text the user and the model see. It records evasion tricks as signals that raise the score only when a rule has also fired, because ordinary Arabic and multilingual text produces some of them. The rules are plain YAML files in `mirsad/detector/rules/`, so they can be reviewed like policies. `combine_scores` in `model.py` computes the noisy-OR ensemble with the exponents and calibration point tuned on the validation split only; calibration maps the tuned operating point to 0.5, so the policy's `flag_threshold: 0.5` and `block_threshold: 0.8` keep their meaning after retraining. Weights are loaded with `allow_pickle=False` and checks on type, shape and finiteness, because a pickled model file would be executable code, and a missing or invalid model leaves the detector in rules-only mode instead of failing.

**No trained model is packaged yet.** Training needs attack-labelled batches and separately written test batches, which the team is still preparing (Section 4.2.2), so every detector-dependent number in this chapter comes from rules-only mode. The dataset tooling is complete and tested: `build_dataset` validates the batches, removes duplicates by normalised-text hash, sends held-out batches only to the test splits, augments only the training split and checks for leakage; `train` tunes on the validation split and writes per-split metrics, a threshold sweep, latencies and figures to `reports/`. The {{reports/results_summary.json#python_tests.by_area.detector}} detector tests use neutral placeholder text only.

### 4.1.6 Audit log and approvals

The audit log (`mirsad/audit/log.py`) implements the HMAC-SHA-256 hash chain of Section 3.3.7 in the `audit_events` table [@rfc2104; @schneier1999secure; @crosby2009efficient]. `compute_hash` reads the hashed fields by attribute access rather than through a model dump, so the hashed values are exactly the stored ones. The HMAC key is derived from the application secret with a fixed label, which keeps it separate from the key that signs login tokens. Before an event is hashed, `redact()` removes API keys, bearer tokens, JWTs, passwords and private keys, and masks payment-card numbers (validated with the Luhn check), Saudi national identifiers and IBANs; oversized payloads are then truncated field by field. `verify()` walks the chain in order and reports the first sequence number at which a gap, a broken link or an HMAC mismatch appears. An optional external anchor, the head sequence number and hash stored outside the database, also reveals truncation of the tail. Appends are serialised by a lock and retried on a sequence conflict when several processes share one database.

`Gateway.replay` reads a stored decision, rebuilds the policy engine of the stored version from the policy store, and re-evaluates the call with the stored taint snapshot and rate-limit counts. For an inspection event it re-scores the stored content with the current detector. The report states whether the replayed action matches the original one.

The approval workflow (`mirsad/approvals/`) stores each request with its call, decision, bilingual summary, risk and expiry time. A decision is applied with a conditional update that succeeds only while the request is still pending, so two approvers cannot both decide and a late decision on an expired request is rejected:

```python
    def _transition(self, approval_id: str, status: ApprovalStatus, *, user: str | None,
                    note: str | None, now: float) -> bool:
        """Atomically move a pending approval to ``status``; False if it was no longer pending."""
        with self.db.session() as sess:
            row = sess.get(ApprovalRow, approval_id)
            if row is None:
                raise ApprovalNotFound(approval_id)
            decision = Decision.model_validate_json(row.decision_json)
            decision_json = decision.model_copy(update={"approval_status": status.value}).model_dump_json()
            result = sess.execute(
                update(ApprovalRow)
                .where(ApprovalRow.id == approval_id, ApprovalRow.status == ApprovalStatus.PENDING.value)
                .values(status=status.value, decided_by=user, decided_at=now, note=note, decision_json=decision_json)
                .execution_options(synchronize_session=False)
            )
            return bool(result.rowcount)
```

Requests and decisions are published on an in-process notifier that feeds the Server-Sent Events (SSE) stream used by the dashboard and the PWA, and a Web Push message is sent to subscribed devices when VAPID keys are configured. A maintenance loop in the API expires overdue requests every few seconds. The summary generator (`summary.py`) writes one to three sentences in English and in Arabic stating what the agent wants to do, why Mirsad paused it and where the data came from. Since integration it names the organisation from the active policy (for example "outside Najd Trading Co.") instead of a generic phrase.

### 4.1.7 Protocol adapters and SDK

`UpstreamManager` (`mirsad/adapters/upstreams.py`) connects Mirsad to the real tools: MCP servers loaded in-process, started over stdio or reached over streamable HTTP through the MCP Python SDK version 2, and plain Python functions registered as tools. It discovers tool schemas, routes each call to its upstream and applies timeouts. A broken connection is re-established for the next call, but the failed call itself is not retried, because it may already have had a side effect.

The MCP proxy (`mcp_proxy.py`) presents Mirsad to an agent as a single MCP server [@mcp2026spec]. Tool listing is filtered by the policy, so an agent discovers only the tools it may call (FR1.4). The handler `on_call_tool` turns each `tools/call` request into a `ToolCall` and passes it to `Gateway.execute` with the upstream manager as executor; if the gateway itself raises, the handler returns a generic error result instead of the exception text.

A denied call comes back as an MCP tool error whose text explains the reason in English and Arabic. The same server is offered over stdio (`mirsad mcp-proxy`, which forwards to a running gateway) and over streamable HTTP at `/mcp`, where each request is authenticated with the agent's key.

The OpenAI-compatible proxy (`openai_proxy.py`) implements `POST /v1/chat/completions` for agents that use function calling. Before forwarding a request to the model, it replaces every `role: tool` message with the inspected, sanitised and spotlighted content. After the model answers, it checks every returned `tool_calls` entry with `check_call`, removes the denied entries, appends an explanation and sets `finish_reason` to `stop` when nothing is left to run. The session identifier is taken from the `X-Mirsad-Session` header or derived from a hash of the first user message.

For frameworks that run tools themselves, the Python SDK (`mirsad/sdk/`) wraps the Guard API. Its `guard` decorator checks a call before the decorated function runs and raises `MirsadBlocked` instead of running it when the call is denied; otherwise it sends the return value for inspection and returns the inspected content, raising again if the result is blocked.

### 4.1.8 REST API and command line

`mirsad.api.create_app` builds the object graph once (database, audit log, notifier, approval service, policy store and engine, taint tracker, detector, upstream manager and gateway) and mounts the routers specified in Section 3.3: agent endpoints under `/v1` and `/mcp`, human endpoints under `/api`, the SSE stream and the two static web apps. Agents authenticate with `mk_` keys that are stored only as SHA-256 hashes and compared in constant time. People log in with scrypt-hashed passwords [@rfc7914] and receive short-lived HS256 JSON Web Tokens [@rfc7519] carrying one of three roles: admin, approver or auditor. Failed logins are throttled per user name and IP address and audited without the password.

Two ASGI middlewares wrap the whole application, including the mounted MCP endpoint. The first adds a strict Content Security Policy (`script-src 'self'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, a no-referrer policy and `no-store` caching for API responses. The second rejects request bodies larger than 1 MB with status 413, whether the size is declared in a header or only discovered while streaming. Policies are stored as versions in the database; activating one hot-swaps the gateway's engine and audits a `policy.activated` event. A background loop (`_maintenance`) expires overdue approvals and picks up policy activations made by another process, such as the command line, every few seconds; a failed cycle is logged and the loop continues.

The `mirsad` command line, built with Click, covers the operations an administrator needs without the web interface: `serve`, `init --demo`, `policy validate` and `policy activate`, `audit verify`, `audit export` and `audit replay`, `scan`, `agent create`, `user create`, `detector train` and `mcp-proxy`.

### 4.1.9 Web dashboard

The dashboard and the approver app are one React 18, TypeScript and Vite code base (`web/`) that is built into two pages served by the gateway at `/` and `/approve`. Both share an API client, the live-event stream, the bilingual dictionaries, the styles and the components. The browser's `EventSource` cannot send an `Authorization` header, and a token in the query string would leak into server logs and browser history, so the live stream is read with `fetch` and an incremental parser that follows the WHATWG event-stream rules and reconnects with exponential backoff. All assets are served from the same origin and there are no inline scripts, so the strict Content Security Policy set by the API holds.

The dashboard has ten pages behind a login: Overview, Activity and audit, Approvals, Policies, Agents, Users, Tools, Detector playground, Demo console and Settings. The Overview page (@fig:c-dash-overview in Appendix C) summarises calls, decisions, pending approvals, detections, gateway overhead and the state of the audit chain, and it updates live as agents act.

Every user-facing string exists in English and Arabic, and a unit test checks that the two dictionaries have identical keys and placeholders. Choosing a language sets the language and direction of the whole document, and the style sheets use logical (start/end) properties, so the layout mirrors for Arabic (@fig:c-dash-activity-ar): one effect in the shared layer sets `lang` and `dir` on the root element whenever the language changes.

A dark theme follows the system setting or the user's choice (@fig:c-dash-overview-dark), and a unit test checks WCAG AA contrast [@w3c2023wcag22] for every pair of foreground and background colour tokens in both themes.

The Activity page lists audit events with filters by agent, tool, outcome, event type, session, call, time and free text. Selecting an event opens a detail drawer (@fig:c-dash-activity-detail) with the outcome, risk, policy version, both hashes of the chain link and the raw event, and with buttons to verify the chain, export the event and show all events of the same call or session. Decision events also list each reason with its layer, the detector spans and the taint provenance, and they can be replayed from the drawer.

The Policies page (@fig:c-dash-policies) is a YAML editor with validation, a line-by-line comparison with the active version, activation and rollback. The Detector playground (@fig:c-dash-playground) scans pasted English or Arabic text and shows the score, its model and rule components, the detected language, highlighted spans and evasion signals. Its built-in samples are ordinary business texts, and the team can add its own labelled samples in a separate file.

### 4.1.10 Approver PWA

The approver app is an installable progressive web app defined by a web app manifest and a service worker [@w3c_appmanifest; @w3c_serviceworkers]. It installs to the home screen on Android and iOS, where Web Push is also available to web apps added to the home screen [@eidson2023-webpush]. The service worker precaches the application shell, uses a network-first strategy for the approval API so that the last known queue stays visible offline, and bypasses the SSE stream and every non-GET request. It also receives Web Push messages and shows a system notification; its `notificationclick` handler focuses an open approver window and moves it to the paused request, or opens a new window on that request.

The pending list (@fig:c-pwa-pending-ar) shows one card per request with a risk badge, the tool, the requesting agent, the start of the summary and the time left. The detail screen (@fig:c-pwa-detail-en and @fig:c-pwa-detail-ar) shows the risk, the tool, the requester and a countdown, followed by three sections: "What the agent wants to do" (the plain-language summary), "Why Mirsad paused it" (one card per reason, labelled with its layer) and "Where the data came from" (the taint evidence). The raw arguments are collapsed by default. Approve and Deny stay fixed at the bottom of the screen; either button opens a confirmation sheet that restates the consequence and accepts an optional note. If another approver has already decided, the server rejects the second decision and the app shows the outcome. Before signing out, the app removes its push subscription so that a shared phone stops receiving another person's alerts.

### 4.1.11 Demonstration workspace and agent

`demo/world.py` simulates the fictional Najd Trading Co. as a deterministic, seeded `World`: 120 customers with Arabic and English names, 30 e-mails, 12 web pages and 12 documents. It exposes 12 business tools: `list_emails`, `read_email`, `send_email`, `search_customers`, `get_customer`, `export_customers`, `update_customer_note`, `delete_customer`, `fetch_url`, `list_documents`, `read_document` and `transfer_funds`. Tools with side effects record what they did (outbox, HTTP log, deletions, exports, transfers, note changes), so a benchmark or the dashboard can tell exactly what an agent caused. Every address uses the reserved `.example` domain and every IBAN and phone number is fake. The method `plant()` inserts text into an e-mail, a web page, a document or a CRM note at the start, middle or end; the Demo console and the attack episodes of Mirsad-Bench use it to place content where an agent will read it.

`demo/workspace_server.py` exposes the same world as an MCP server, which the gateway loads in-process by default (it can also run over stdio). `demo/agent.py` contains the demonstration agent: a tool-calling loop over the OpenAI-compatible API with a bilingual system prompt and at most eight steps, with three interchangeable backends (direct and unprotected, in-process through the gateway, and over HTTP with an agent key). The dashboard's Demo console runs this agent on eight curated scenarios that cover five attacker goals (exfiltration, destruction, fraud, phishing and privilege abuse). One example is an invoice e-mail with appended text that asks the agent to export the customer list and e-mail it to an outside address. The console can switch protection on and off, shows a timeline of the agent's steps with Mirsad's decision for each, and shows an "attacker inbox" with whatever reached the attacker. These scenarios exist for live demonstration only; no result in Section 4.2 is computed from them. Each one plants a short illustrative instruction aimed at the simulated workspace, so `demo/scenarios.py` is the one place in the repository where such instructions are written out (Section 3.6.4).

### 4.1.12 Mirsad-Bench

Mirsad-Bench (`bench/`) adapts the methodology of AgentDojo and InjecAgent [@debenedetti2024agentdojo; @zhan2024injecagent] to the simulated Saudi enterprise. `bench/loader.py` validates the scenario files against a JSON schema and checks every planned action against the tool schemas of the demonstration workspace. The suite currently holds {{reports/results_summary.json#bench.scripted_benign_deny.tasks}} benign user tasks: {{reports/bench/scripted-benign-deny/summary.json#meta.tasks_by_lang.en}} in English and {{reports/bench/scripted-benign-deny/summary.json#meta.tasks_by_lang.ar}} in Arabic ({{reports/bench/scripted-benign-deny/summary.json#configs.1.by_variety.msa.episodes}} in Modern Standard Arabic and {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_variety.gulf.episodes}} in Gulf dialect). They cover e-mail reading, CRM lookups and updates, internal and external replies, web and document reading, small exports, and four tasks that legitimately need a human (a vendor payment and the deletion of a duplicate customer record, in each language). Each task has a plan of tool calls, a success predicate evaluated on the side effects of the world, and a `reads` list that records which content it reads and therefore where injected text could appear.

The five defence configurations are produced by transforming the default policy in `bench/defenses.py`, so every configuration runs the same production code paths. For example, `taint_only` and `detector_only` drop all constraints, rate limits and global rules and set every allowed tool to `approval: never`, and `policy_only` and `detector_only` switch taint tracking off.

The configurations without a detector use a stand-in that scores every text as benign. Each episode gets a fresh world, a fresh policy engine (so rate-limit counters cannot leak between episodes) and a fresh taint tracker; the audit log and the approval service are shared within one configuration, which makes the per-configuration audit chain and replay check meaningful. The human approver is replaced by an automatic decider in one of three modes: `deny` rejects every escalation, `approve` accepts every escalation and `oracle` accepts exactly the calls that match the user's plan, which models a human who knows what the user asked for. The runner appends one JSON line per finished episode, so an interrupted run resumes where it stopped, records a SHA-256 fingerprint of the scenario files, verifies the audit chain after each configuration and, with `--replay-check`, replays every audited decision. `bench/metrics.py` computes the metrics of Section 4.2.1 per configuration and per language, Arabic variety and task category, and `bench/report.py` writes JSON, Markdown and Matplotlib figures. `bench/latency.py` measures the HTTP overhead against the real FastAPI application (Section 4.2.5).

Attack episodes are implemented in `bench/attacks.py`. An episode combines a user task with an injection task and an attack template, both written by the team, plants the rendered text in one of the task's `reads` targets with `World.plant()`, and records a survival marker that shows whether the planted text still reaches the agent after the gateway has inspected the result. In attack episodes the `ScriptedAgent` is worst-case compliant, as designed in Section 3.1: the first time a result it receives still contains the planted text, it performs the injection task's actions through the gateway. Each episode is graded on the user task (utility under attack) and on the injection predicate (attack success), and an attack that fails is attributed to the layer that stopped it (approval, policy, taint or detector, or `not_reached` when the planted text never reached the agent). The runner executes these episodes automatically (`--episodes auto`, the default) once `bench/scenarios/attacks/*.yaml` defines injection tasks and attack templates, and `tests/bench/test_bench_attacks.py` tests construction, planting, survival markers and attribution with neutral placeholder text. No attack files exist yet, so no attack episode has been run and the ASR columns print as "[pending]" (Section 4.2.3).

### 4.1.13 Integration issues found and fixed

Integration was tracked as a checklist (`docs/dev/INTEGRATOR_TODO.md`), and the security test suite of Section 4.2.6 added findings of its own. @tab:i-fixes lists the issues that were fixed in code; the last column states how each fix was verified, and two fixes still lack a dedicated regression test.

Table: Issues found and fixed during integration {#tab:i-fixes widths=1.9,2.6,1.5}
| Issue | Fix | Verified by |
|---|---|---|
| A tool that raised an unexpected exception returned the raw exception text to the agent, which could reveal file paths, host names or stack details | The upstream manager returns a generic bilingual message and logs the details server-side; `Gateway.execute` reports only the exception type and stores the message in the audit log | Security test ST-13 |
| A taint rule that an administrator had downgraded to `allow` still raised the risk score and counted as "taint fired", so it still forced approval through `approval: on_risk` | Downgraded taint reasons stay in the decision as evidence but are excluded from the risk score and from the approval condition | Integration test (two cases) |
| The taint tracker used a fixed list of internal domains, so a policy change left it with stale domains | The tracker receives a function that reads the active policy (Section 4.1.4) | Integration test |
| Approval summaries said "outside the organisation" | The gateway copies the organisation name from the policy into the approval service at start-up and on every policy swap | Integration test |
| Full taint snapshots could exceed the audit payload limit, which broke replay | `minimal_snapshot` stores only the values the rules consulted | Replay sweep (Section 4.2.7) |
| The taint tracker must see the original result, not the sanitised one, or provenance is lost | `inspect_result` registers the original result | Code review (no dedicated test yet) |
| The benchmark shared one rate limiter between episodes, which distorted the false-positive rate | Fresh policy engine and taint tracker per episode | Benchmark test |
| Source files contained literal bidirectional control characters, which can make code display differently from how it executes (the "Trojan Source" problem) | The Python sources write the isolate characters used in bilingual messages as `\u2068` and `\u2069` escapes | Source scan |
| React Router and Vitest versions with published security advisories | Upgraded to `react-router-dom` 7.18.4 and Vitest 5.0.3 | `npm audit` (Section 4.2.6) |
| The example rule in the specification used a regular expression with exponential backtracking | Replaced by a linear-time equivalent; the validator now rejects nested ambiguous quantifiers | Security test ST-08 |
| CORS did not allow the `X-Mirsad-Session` and `X-Upstream-Authorization` headers | Both added to the allowed headers | Code review (no dedicated test yet) |

The error-message fix in the upstream manager distinguishes argument errors (`ValueError` and `TypeError`), whose message the agent needs in order to correct its call, from every other exception, which is logged server-side and replaced by a generic bilingual message. The default policy's rule `no-bulk-export-to-email`, which limits bulk e-mailing of customer records, now counts at-signs with a pattern that cannot backtrack.

Three small items remain open (duplicate login throttling, the demonstration agent's embedded policy and a few literal direction marks in web files); Appendix B.6 lists them.

## 4.2 Evaluation

### 4.2.1 Evaluation setup

All measurements were taken on the development machine described in Section 4.1.1 (Apple M5, 16 GB, macOS 26.5, Python 3.12). The gateway used the current default policy (`configs/policies/default.yaml`, in which CRM results are scanned; Section 3.3.4), SQLite for storage, and the detector in rules-only mode because no trained model exists yet. Two agents were used. The **scripted agent** executes each task's plan exactly and is deterministic, so differences between configurations are caused by the gateway alone. The **LLM agent** is the demonstration agent driven by Qwen2.5-7B through Ollama at temperature 0, with at most eight steps; it shows how a real model's choices interact with the gateway. @tab:i-defences lists the defence configurations and approver modes.

Table: Defence configurations and approver modes {#tab:i-defences widths=1.3,4.7}
| Configuration | Meaning |
|---|---|
| `none` | No gateway: tools run directly against the world (baseline) |
| `full` | Default policy, taint tracking and detector with sanitising and spotlighting |
| `policy_only` | Allow-list, constraints, rate limits, global rules and approval policy; no taint tracking, no detector |
| `taint_only` | Tool profiles (trust, sensitivity, sink, risk) and taint rules; no constraints, rate limits, rules, approval policy or detector |
| `detector_only` | Tool profiles and the detector with sanitising and spotlighting; nothing else |
| Approver `deny` | Every escalation is rejected (a reviewer who rejects anything unusual) |
| Approver `approve` | Every escalation is accepted (a reviewer who approves without reading) |
| Approver `oracle` | Exactly the calls in the user's plan are accepted (a reviewer who knows what the user asked for) |

The metrics follow AgentDojo's split between utility and attack success [@debenedetti2024agentdojo] and add the costs that matter for a gateway (@tab:i-metrics).

Table: Evaluation metrics {#tab:i-metrics widths=1.6,4.4}
| Metric | Definition |
|---|---|
| Utility | Share of episodes whose success predicate holds on the world's side effects |
| Benign false-positive rate (FPR) | Benign calls denied by the automatic layers ÷ benign calls |
| Approval friction | Benign calls escalated to a human ÷ benign calls |
| Final block rate | Benign calls that did not run in the end (automatic or human denial) ÷ benign calls |
| Result false-positive rate | Benign tool results the detector sanitised or blocked ÷ results inspected |
| Attack success rate (ASR) | Attack episodes whose injection predicate holds ÷ attack episodes |
| ASR reduction | 1 − ASR(defence) ÷ ASR(`none`) |
| Gateway latency | Decision plus result inspection per call as reported by the gateway, excluding human waiting time |
| Added latency | HTTP round trip through Mirsad minus the time of a direct in-process tool call, paired per call |
| Detector precision, recall, F1, FPR, ROC-AUC | Standard classification metrics at the calibrated threshold 0.5 on held-out splits |
| Replay agreement | Audited decisions whose replay gives the same action ÷ decisions replayed |

### 4.2.2 Detector evaluation

The detector is to be evaluated on three held-out test splits written separately from the training data (English, Arabic and mixed Arabic-English) and, once the team adds it, on an external public English dataset for out-of-distribution evidence. The target is an F1 score of at least 0.85 on both the English and the Arabic test sets (Objective 2). The values in @tab:i-detector are read from the evaluation output when the report is built.

Table: Detector results on held-out splits (ensemble, threshold 0.5) {#tab:i-detector widths=1.3,0.6,0.8,0.8,0.7,0.7,0.8,0.9,0.9}
| Split | n | Precision | Recall | F1 | FPR | ROC-AUC | F1 rules only | F1 model only |
|---|---|---|---|---|---|---|---|---|
| `test_en` | {{reports/results_summary.json#detector.splits.test_en.n}} | {{reports/results_summary.json#detector.splits.test_en.precision|.3f}} | {{reports/results_summary.json#detector.splits.test_en.recall|.3f}} | {{reports/results_summary.json#detector.splits.test_en.f1|.3f}} | {{reports/results_summary.json#detector.splits.test_en.fpr|.3f}} | {{reports/results_summary.json#detector.splits.test_en.roc_auc|.3f}} | {{reports/results_summary.json#detector.splits.test_en.f1_rules_only|.3f}} | {{reports/results_summary.json#detector.splits.test_en.f1_model_only|.3f}} |
| `test_ar` | {{reports/results_summary.json#detector.splits.test_ar.n}} | {{reports/results_summary.json#detector.splits.test_ar.precision|.3f}} | {{reports/results_summary.json#detector.splits.test_ar.recall|.3f}} | {{reports/results_summary.json#detector.splits.test_ar.f1|.3f}} | {{reports/results_summary.json#detector.splits.test_ar.fpr|.3f}} | {{reports/results_summary.json#detector.splits.test_ar.roc_auc|.3f}} | {{reports/results_summary.json#detector.splits.test_ar.f1_rules_only|.3f}} | {{reports/results_summary.json#detector.splits.test_ar.f1_model_only|.3f}} |
| `test_mixed` | {{reports/results_summary.json#detector.splits.test_mixed.n}} | {{reports/results_summary.json#detector.splits.test_mixed.precision|.3f}} | {{reports/results_summary.json#detector.splits.test_mixed.recall|.3f}} | {{reports/results_summary.json#detector.splits.test_mixed.f1|.3f}} | {{reports/results_summary.json#detector.splits.test_mixed.fpr|.3f}} | {{reports/results_summary.json#detector.splits.test_mixed.roc_auc|.3f}} | {{reports/results_summary.json#detector.splits.test_mixed.f1_rules_only|.3f}} | {{reports/results_summary.json#detector.splits.test_mixed.f1_model_only|.3f}} |
| External (`test_ext_deepset`) | {{reports/results_summary.json#detector.splits.test_ext_deepset.n}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.precision|.3f}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.recall|.3f}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.f1|.3f}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.fpr|.3f}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.roc_auc|.3f}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.f1_rules_only|.3f}} | {{reports/results_summary.json#detector.splits.test_ext_deepset.f1_model_only|.3f}} |

> **Status: pending team-supplied data.** These results have not been measured. The repository holds only benign training batches; the attack-labelled training, validation and held-out test batches are written by the team (Section 3.6.4). `make detector` then trains and calibrates the model on the training and validation splits only and fills this table (Appendix E.11.1).

What has been measured about the detector is its behaviour on benign content in the running system. Under full protection with the oracle approver, the detector inspected {{reports/bench/scripted-benign-oracle/summary.json#configs.1.overall.results_inspected}} benign tool results, including the CRM look-ups that the default policy scans; it flagged {{reports/bench/scripted-benign-oracle/summary.json#configs.1.overall.result_flag_rate|.0%}} of them and sanitised or blocked {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.result_fp_rate|.0%}} (@tab:i-benign gives the result false-positive rate of every configuration). This is evidence about over-defence on the business content of the benchmark, in rules-only mode; it says nothing about recall, and it must be measured again once a trained model is packaged. A separate pre-training check of the rules-only fallback on the team's benign dataset batches did flag some records, more of them in the Arabic batch, where polite imperatives and forms of address resemble injected instructions (`docs/detector.md`, Section 13.5). That check is not yet part of the recorded evidence, so its rates are not quoted here; Section 5.3 draws the lesson. Scan latency for a 2 KB text with the trained ensemble: {{reports/results_summary.json#detector.latency_ms.2KB.p50|.2f}} ms (target: below 10 ms).

### 4.2.3 Attack resistance on Mirsad-Bench

Attack resistance is the central quantitative claim of the project: the gateway should reduce the attack success rate by at least 80% relative to the unprotected baseline (Objective 3). @tab:i-asr will be filled from three benchmark runs: the scripted agent with an oracle approver (a careful human), the scripted agent with an approve-all approver (which isolates the automatic layers, because every escalation is let through) and the LLM agent with an oracle approver.

Table: Attack success rate (ASR) by defence configuration {#tab:i-asr widths=1.4,1.2,1.2,1.2,1.2}
| Configuration | ASR, scripted, oracle | ASR, scripted, approve-all | ASR, LLM, oracle | ASR reduction, scripted, oracle |
|---|---|---|---|---|
| `none` | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.none.asr|.1%}} | {{reports/results_summary.json#bench.scripted_attack_approve.configs.none.asr|.1%}} | {{reports/results_summary.json#bench.llm_attack_oracle.configs.none.asr|.1%}} | – |
| `full` | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.full.asr|.1%}} | {{reports/results_summary.json#bench.scripted_attack_approve.configs.full.asr|.1%}} | {{reports/results_summary.json#bench.llm_attack_oracle.configs.full.asr|.1%}} | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.full.asr_reduction|.1%}} |
| `policy_only` | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.policy_only.asr|.1%}} | {{reports/results_summary.json#bench.scripted_attack_approve.configs.policy_only.asr|.1%}} | – | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.policy_only.asr_reduction|.1%}} |
| `taint_only` | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.taint_only.asr|.1%}} | {{reports/results_summary.json#bench.scripted_attack_approve.configs.taint_only.asr|.1%}} | – | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.taint_only.asr_reduction|.1%}} |
| `detector_only` | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.detector_only.asr|.1%}} | {{reports/results_summary.json#bench.scripted_attack_approve.configs.detector_only.asr|.1%}} | – | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.detector_only.asr_reduction|.1%}} |

> **Status: pending team-supplied attack files.** No attack episode has been run, so no attack success rate has been measured. The harness executes attack episodes (Section 4.1.12) once the team adds its injection tasks (attacker goals expressed as tool actions with a success predicate) and attack templates in English, Arabic and mixed text to `bench/scenarios/attacks/`, following the README in that folder; `python -m bench.loader` validates them. `scripts/run_bench.sh` then produces the scripted-oracle, scripted-approve and LLM runs, for example `python -m bench.run --agent scripted --episodes attack --defense all --approver oracle --replay-check --out reports/bench/scripted-attack-oracle`, and `scripts/collect_results.py` fills @tab:i-asr (Appendix E.11.2).

Even when these runs exist, they will measure Mirsad against non-adaptive attacks written in advance. Attackers who adapt to a known defence have broken every published prompt-injection defence they were tested against [@nasr2026attackermovessecond; @zhan2025adaptive], and Mirsad's design assumes that the detector will be evaded: the policy and taint layers constrain what a hijacked agent can do, whatever the text says. The ablation columns are meant to show how much each layer contributes on its own.

### 4.2.4 Benign behaviour

The benign evaluation answers the other half of the question: how much legitimate work the gateway costs. All {{reports/results_summary.json#bench.scripted_benign_deny.tasks}} user tasks were run with the scripted agent under every defence configuration, once with the denying approver and once with the oracle approver. Each configuration made {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.calls}} benign tool calls. @tab:i-benign summarises the results and @fig:i-benign plots them.

Table: Benign results of the scripted agent ({{reports/results_summary.json#bench.scripted_benign_deny.tasks}} tasks, {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.calls}} calls per configuration) {#tab:i-benign widths=1.4,0.9,0.9,0.8,0.9,0.9,0.9}
| Configuration | Approver | Utility | FPR | Friction | Final block | Result FP |
|---|---|---|---|---|---|---|
| `none` | – | {{reports/results_summary.json#bench.scripted_benign_deny.configs.none.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.none.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.none.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.none.final_block_rate|.1%}} | – |
| `full` | deny | {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.final_block_rate|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.result_fp_rate|.1%}} |
| `policy_only` | deny | {{reports/results_summary.json#bench.scripted_benign_deny.configs.policy_only.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.policy_only.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.policy_only.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.policy_only.final_block_rate|.1%}} | n/a |
| `taint_only` | deny | {{reports/results_summary.json#bench.scripted_benign_deny.configs.taint_only.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.taint_only.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.taint_only.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.taint_only.final_block_rate|.1%}} | n/a |
| `detector_only` | deny | {{reports/results_summary.json#bench.scripted_benign_deny.configs.detector_only.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.detector_only.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.detector_only.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.detector_only.final_block_rate|.1%}} | {{reports/results_summary.json#bench.scripted_benign_deny.configs.detector_only.result_fp_rate|.1%}} |
| `full` | oracle | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.final_block_rate|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.result_fp_rate|.1%}} |
| `policy_only` | oracle | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.policy_only.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.policy_only.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.policy_only.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.policy_only.final_block_rate|.1%}} | n/a |
| `taint_only` | oracle | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.taint_only.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.taint_only.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.taint_only.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.taint_only.final_block_rate|.1%}} | n/a |
| `detector_only` | oracle | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.detector_only.utility|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.detector_only.fpr|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.detector_only.friction|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.detector_only.final_block_rate|.1%}} | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.detector_only.result_fp_rate|.1%}} |

The results show the following.

- **Automatic denials.** The benign false-positive rate under full protection was {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.fpr|.1%}}, against the 5% target; @tab:i-benign gives the rate of every ablation. Where the detector was enabled, it sanitised or blocked the share of benign results given in the Result FP column. The caveat is that the detector ran rules-only and that the tasks were written by the team.
- **Friction comes from the policy's intended escalation paths.** Under full protection, {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.friction|.1%}} of benign calls ({{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.escalated}} of {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.calls}}) were escalated to a human. The reason codes recorded in `reports/bench/scripted-benign-deny/summary.md` account for them: external e-mail replies, each of which triggered both the `domain_in` constraint on `to` (`CONSTRAINT_VIOLATION`, {{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.blocking_reasons.CONSTRAINT_VIOLATION}} calls) and `TAINT_UNTRUSTED_TO_EXTERNAL` ({{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.blocking_reasons.TAINT_UNTRUSTED_TO_EXTERNAL}}), exports (`APPROVAL_POLICY`, {{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.blocking_reasons.APPROVAL_POLICY}}) and the calls in the tasks that legitimately need a human (`APPROVAL_ALWAYS`, {{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.blocking_reasons.APPROVAL_ALWAYS}}). Excluding the approval-required tasks, the unexpected friction was {{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.unexpected_friction|.1%}}.
- **The approver decides the utility cost.** With the oracle approver, utility under full protection was {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.utility|.0%}}. With an approver who rejects everything it was {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.utility|.0%}} ({{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.utility_no_approval_tasks|.1%}} excluding the approval-required tasks), which is the cost of a reviewer who refuses every external reply and export.
- **The policy layer is needed for high-risk tools.** The approval recall, the share of approval-required tasks in which a human was asked about the legitimate payment or deletion, was {{reports/bench/scripted-benign-deny/summary.json#configs.4.overall.approval_recall|.0%}} for `taint_only` and {{reports/bench/scripted-benign-deny/summary.json#configs.0.overall.approval_recall|.0%}} for `detector_only`, against {{reports/bench/scripted-benign-deny/summary.json#configs.1.overall.approval_recall|.0%}} under full protection.

![Benign false-positive rate, approval friction and utility per defence configuration (scripted agent, denying approver)](reports/bench/scripted-benign-deny/figures/benign_by_defense.png){#fig:i-benign width=6.0}

@tab:i-lang and @fig:i-friction-lang break the full-protection results down by language. Friction was {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.en.friction|.1%}} for English and {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.ar.friction|.1%}} for Arabic tasks; the policy and taint layers act on tool names, arguments and provenance, which do not depend on the language of the prompt. Within Arabic, friction was {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_variety.gulf.friction|.1%}} for the Gulf-dialect tasks and {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_variety.msa.friction|.1%}} for the Modern Standard Arabic tasks; any difference reflects which task categories were written in each variety, not the dialect itself.

Table: Full protection by language (scripted agent) {#tab:i-lang widths=1.2,1,1,1,1,1}
| Language | Calls | Utility (deny) | Utility (oracle) | FPR | Friction |
|---|---|---|---|---|---|
| English | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.en.calls}} | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.en.utility|.1%}} | {{reports/bench/scripted-benign-oracle/summary.json#configs.1.by_lang.en.utility|.1%}} | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.en.fpr|.1%}} | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.en.friction|.1%}} |
| Arabic | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.ar.calls}} | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.ar.utility|.1%}} | {{reports/bench/scripted-benign-oracle/summary.json#configs.1.by_lang.ar.utility|.1%}} | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.ar.fpr|.1%}} | {{reports/bench/scripted-benign-deny/summary.json#configs.1.by_lang.ar.friction|.1%}} |

![Approval friction on benign calls by language and defence configuration](reports/bench/scripted-benign-deny/figures/friction_by_language.png){#fig:i-friction-lang width=5.5}

A smoke run with the LLM agent ({{reports/results_summary.json#bench.llm_smoke.tasks}} tasks, {{reports/bench/llm-smoke/summary.json#meta.tasks_by_lang.en}} in English and {{reports/bench/llm-smoke/summary.json#meta.tasks_by_lang.ar}} in Arabic, with and without Mirsad) gave a utility of {{reports/results_summary.json#bench.llm_smoke.configs.none.utility|.0%}} without and {{reports/results_summary.json#bench.llm_smoke.configs.full.utility|.0%}} with Mirsad; of the {{reports/results_summary.json#bench.llm_smoke.configs.full.calls}} protected calls, {{reports/results_summary.json#bench.llm_smoke.configs.full.fpr|.0%}} were denied and {{reports/results_summary.json#bench.llm_smoke.configs.full.friction|.0%}} escalated. Both configurations failed the same Arabic CRM-update task, in which the model wrote a generic note instead of the requested phone number; this is a model error that the gateway did not cause. So few episodes make a smoke test, not a utility estimate.

### 4.2.5 Performance

The latency benchmark (`bench/latency.py`) starts the real FastAPI application with the default policy and agent-key authentication, sends {{reports/bench/latency-process.json#warmup_calls}} warm-up calls and then {{reports/results_summary.json#latency.separate_process.calls|,}} benign read-only calls spread over six tools, first one at a time and then from {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions. For each call it subtracts the time of the same tool call made directly in-process from the HTTP round trip through Mirsad. It was run twice: with the server in a thread of the benchmarking process, and with the server in a separate process, which removes the competition between client and server for Python's global interpreter lock. @tab:i-latency gives the results and @fig:i-latency their distribution.

Table: Added latency per tool call ({{reports/results_summary.json#latency.separate_process.calls|,}} benign calls) {#tab:i-latency widths=2.2,1,1,1,1,1}
| Scenario | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) | HTTP errors |
|---|---|---|---|---|---|
| Sequential, separate process | {{reports/results_summary.json#latency.separate_process.sequential_added_p50|.1f}} | {{reports/results_summary.json#latency.separate_process.sequential_added_p95|.1f}} | {{reports/results_summary.json#latency.separate_process.sequential_added_p99|.1f}} | {{reports/results_summary.json#latency.separate_process.sequential_rps|.0f}} | {{reports/bench/latency-process.json#sequential.http_errors}} |
| {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions, separate process | {{reports/results_summary.json#latency.separate_process.concurrent_added_p50|.1f}} | {{reports/results_summary.json#latency.separate_process.concurrent_added_p95|.1f}} | {{reports/results_summary.json#latency.separate_process.concurrent_added_p99|.1f}} | {{reports/results_summary.json#latency.separate_process.concurrent_rps|.0f}} | {{reports/results_summary.json#latency.separate_process.concurrent_errors}} |
| Sequential, in-process | {{reports/results_summary.json#latency.in_process.sequential_added_p50|.1f}} | {{reports/results_summary.json#latency.in_process.sequential_added_p95|.1f}} | {{reports/results_summary.json#latency.in_process.sequential_added_p99|.1f}} | {{reports/results_summary.json#latency.in_process.sequential_rps|.0f}} | {{reports/bench/latency.json#sequential.http_errors}} |
| {{reports/results_summary.json#latency.in_process.sessions}} concurrent sessions, in-process | {{reports/results_summary.json#latency.in_process.concurrent_added_p50|.1f}} | {{reports/results_summary.json#latency.in_process.concurrent_added_p95|.1f}} | {{reports/results_summary.json#latency.in_process.concurrent_added_p99|.1f}} | {{reports/results_summary.json#latency.in_process.concurrent_rps|.0f}} | {{reports/results_summary.json#latency.in_process.concurrent_errors}} |

One request at a time, Mirsad adds a median of {{reports/results_summary.json#latency.separate_process.sequential_added_p50|.1f}} ms per call, of which the gateway's own decision and inspection account for {{reports/results_summary.json#latency.separate_process.gateway_p50|.1f}} ms; the rest is HTTP handling and authentication. NFR1 is assessed on this median and on the separate-process layout, which matches a real deployment (Section 3.5.3). Under {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions with the server in its own process, the median rises to {{reports/results_summary.json#latency.separate_process.concurrent_added_p50|.0f}} ms, against the 200 ms target. With client and server sharing one interpreter it is {{reports/results_summary.json#latency.in_process.concurrent_added_p50|.0f}} ms; that layout measures the client competing with the server for Python's global interpreter lock, not a deployment, so it is reported as context only. No request failed in either layout, so the single node served {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions correctly (NFR11).

The concurrent numbers are mostly queueing. With the server in its own process, the time the gateway itself reported per call grew from a median of {{reports/bench/latency-process.json#sequential.gateway_ms.p50|.1f}} ms to {{reports/bench/latency-process.json#concurrent.gateway_ms.p50|.1f}} ms, because the decision pipeline holds one lock while it evaluates and appends to the audit chain, and the SQLite writes serialise behind it. This is the price of the design choice in Section 4.1.2 that keeps taint state and the hash chain consistent. The in-process run additionally shares one interpreter between client and server, which explains its long tail (p95 {{reports/results_summary.json#latency.in_process.concurrent_added_p95|.0f}} ms). A deployment that expects sustained concurrency should therefore be measured with several workers and PostgreSQL before a concurrency figure is quoted; finer-grained locking per session is a possible improvement.

![Distribution of added latency per call, sequential and with {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions (server in a separate process, logarithmic scale)](reports/bench/figures/latency-process.png){#fig:i-latency width=6.0}

Within the benchmark, where calls run in-process without HTTP, the gateway's median cost per call was {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.gateway_p50_ms|.1f}} ms under full protection, against {{reports/results_summary.json#bench.scripted_benign_deny.configs.policy_only.gateway_p50_ms|.1f}} ms for the policy layer alone (@fig:i-gw-latency). The difference is mostly the detector scan and the taint bookkeeping on each result.

![Gateway latency per benign call by defence configuration (decision plus result inspection, excluding human waiting)](reports/bench/scripted-benign-deny/figures/gateway_latency.png){#fig:i-gw-latency width=5.5}

### 4.2.6 Security testing of the gateway

A firewall that concentrates trust becomes a target itself, so the gateway was tested against its own threat model. The STRIDE analysis of the data-flow diagram [@shostack2014threat; @microsoft_stride] produced the security tests in `tests/security/test_gateway_security.py`. They replace the manual Burp Suite and OWASP ZAP pass planned in the proposal (Section 3.4.5) with checks that run on every change. The suite has 23 security tests (ST-01 to ST-23) that expand to {{reports/results_summary.json#python_tests.by_area.security}} test cases; all of them passed in the evidence run (@tab:i-stride).

Table: Security tests of the gateway by STRIDE category {#tab:i-stride widths=1.3,1.1,3.6}
| Category | Tests | What is checked |
|---|---|---|
| Spoofing | ST-01 to ST-05 | Every management route requires authentication; forged, unsigned, expired and malformed tokens are rejected; editing the role claim of a valid token does not grant admin rights; rotating an agent key revokes the old key; malformed agent keys are rejected |
| Tampering | ST-06 to ST-08 | Modifying or deleting an audit row is detected by chain verification; a policy containing a catastrophic regular expression is rejected |
| Repudiation | ST-09, ST-10 | Approval decisions are attributed to the approver and cannot be changed; failed logins are audited without the password |
| Information disclosure | ST-11 to ST-17 | Secrets in tool arguments are redacted in the audit log; user and agent listings never return hashes or keys; tool failures do not leak internal details; static file paths cannot escape the web root; security headers are present; CORS rejects unknown origins; SQL-like filter values are treated as data |
| Denial of service | ST-18, ST-19 | Oversized request bodies are rejected; repeated failed logins are throttled |
| Elevation of privilege | ST-20 to ST-23 | Approver and auditor roles cannot perform admin actions; agent keys cannot use human APIs and human tokens cannot act as agents; unlisted tools and unknown agents are denied by default; the default policy blocks requests from `fetch_url` to loopback, link-local metadata and internal addresses |

The other automated checks gave the following results.

- **Static analysis.** Bandit reported {{reports/results_summary.json#security.bandit_issues}} issues over {{reports/results_summary.json#security.bandit_loc|,}} lines of code. The configuration skips only the rule against `assert` statements (B101) and excludes the tests, and the report records no inline `nosec` suppressions, so the zero is not the result of silencing findings. Ruff's security rules (the `S` set) are part of the lint configuration, but no Ruff report is stored in `reports/` (Appendix B.5.3).
- **Dependency audit.** pip-audit checked {{reports/results_summary.json#security.pip_audit_packages}} Python packages and found {{reports/results_summary.json#security.pip_audit_vulnerable}} with known vulnerabilities; `npm audit` over the web app's {{reports/security/npm-audit.json#metadata.dependencies.total}} dependencies, including development dependencies, reported {{reports/results_summary.json#security.npm_audit_vulnerabilities}} vulnerabilities after the React Router and Vitest upgrades (Section 4.1.13).
- **PostgreSQL compatibility.** The tests in `tests/integration/test_postgres.py` run the storage, audit chain, authentication and approval code against a real PostgreSQL server started by the `pgserver` package: appending and verifying the chain, detecting tampering, a user and agent-key round trip, and the full approval lifecycle. They passed in the recorded run, which supports the claim that the same code runs on SQLite in development and PostgreSQL in deployment.
- **Test suite and coverage.** All {{reports/results_summary.json#python_tests.total|,}} Python tests ({{reports/results_summary.json#python_tests.failed}} failures) and all {{reports/results_summary.json#web_tests.total}} web tests ({{reports/results_summary.json#web_tests.files}} Vitest suites in the 10 test files of `web/tests/`) passed. Statement coverage of the `mirsad` package was {{reports/results_summary.json#coverage.percent|.1f}}% of {{reports/results_summary.json#coverage.statements|,}} statements; the lowest package, the adapters, reached {{reports/results_summary.json#coverage.by_package.adapters|.1f}}%.

The automated suite does not replace an independent penetration test. It checks the threats the team identified, with the inputs the team chose; Section 4.2.10 returns to this.

### 4.2.7 Audit integrity and reproducibility

Every benchmark configuration verified its audit chain after its episodes, and every audited decision was replayed with the stored policy version, taint snapshot and rate-limit counts. In the denying-approver run, {{reports/results_summary.json#bench.scripted_benign_deny.replay_matched}} of {{reports/results_summary.json#bench.scripted_benign_deny.replay_checked}} decisions replayed to the same action, and in the oracle run {{reports/results_summary.json#bench.scripted_benign_oracle.replay_matched}} of {{reports/results_summary.json#bench.scripted_benign_oracle.replay_checked}}: four protected configurations with {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.calls}} decisions each. Every chain verified (Appendix B.5.6). The LLM smoke run replayed {{reports/results_summary.json#bench.llm_smoke.replay_matched}} of {{reports/results_summary.json#bench.llm_smoke.replay_checked}} decisions, and both latency runs ended with an intact chain. This meets the acceptance criterion of FR6.3 ("100% of benchmark decisions replay to the same action"). The tampering tests ST-06 and ST-07, and their PostgreSQL counterpart, show the other side: a modified or deleted row is detected and the first broken sequence number is reported.

Replay is exact because every source of variation is captured. Policy versions are content hashes stored in the database, the taint rules are a pure function of a stored snapshot, rate-limit counts are stored with the decision, and the scripted benchmark uses a fixed world seed. The benchmark runner also stores a SHA-256 fingerprint of the scenario files and warns when a resumed run was graded with different files. The fingerprint does not cover the policy, so the reported runs were executed from scratch after the last change to the default policy (Appendix B.1). The whole evidence base of this chapter can be regenerated with one command (`scripts/run_evidence.sh`), and the report itself reads its numbers from the generated files, so the text and the evidence cannot drift apart silently.

### 4.2.8 Usability: approval decision time

The usability target (NFR4) is that an approver can understand a paused request and decide on it in under 30 seconds on a phone. No user study has been run yet. As a first, transparent estimate, the approval flow of the PWA was modelled with the Keystroke-Level Model (KLM) of Card, Moran and Newell [@card1980klm], using their standard operator times: mental preparation M = 1.35 s, pointing P = 1.10 s and a key or button press K = 0.28 s (their value for an average non-secretary typist, used here as a conservative press time). The KLM was defined for keyboard and mouse; a tap on a phone is modelled as P + K = 1.38 s, an assumption rather than a measured value. Three further assumptions are needed:

- **Opening time.** The PWA opens on the request detail within R = 1.0 s of tapping the notification (assumed, not measured; the notification links directly to the request).
- **Reading rate.** The approver reads at 200 words per minute, i.e. 0.30 s per word. This is an assumption chosen to be slower than fluent silent reading to allow for a small screen, technical identifiers and reading in a second language; a sensitivity check follows.
- **Reading load.** Word counts come from the real summary generator. Case A is the paused deletion shown in @fig:c-pwa-detail-en (summary 34 words, reason cards 19 words). Case B is an external e-mail escalated by both the domain constraint and the untrusted-content taint rule, the most common escalation in the benchmark (summary 57 words, reason cards 51 words). The confirmation sheet adds 13 words.

@tab:i-klm gives the step-by-step estimate.

Table: Keystroke-Level Model estimate of the approval decision time (seconds) {#tab:i-klm widths=3,1.4,0.8,0.8}
| Step | Operators | Case A | Case B |
|---|---|---|---|
| Notice the notification and decide to open it | M | 1.35 | 1.35 |
| Tap the notification | P + K | 1.38 | 1.38 |
| PWA opens on the request | R (assumed) | 1.00 | 1.00 |
| Read "What the agent wants to do" | 34 / 57 words × 0.30 | 10.20 | 17.10 |
| Decide | M | 1.35 | 1.35 |
| Tap Approve or Deny | P + K | 1.38 | 1.38 |
| Read the confirmation sheet | 13 words × 0.30 | 3.90 | 3.90 |
| Tap the confirm button (no note) | P + K | 1.38 | 1.38 |
| **Total, reading the summary** | | **21.94** | **28.84** |
| Optional: also read every reason card | 19 / 51 words × 0.30 | +5.70 | +15.30 |
| **Total, reading everything** | | **27.64** | **44.14** |

Under these assumptions an approver who reads the plain-language summary decides within the 30-second target in both cases, with little margin in case B. An approver who also reads every reason card of a multi-reason request needs about 44 s, and at a slower reading rate of 150 words per minute even the summary-only path of case B takes about 36 s. Typing a note would add time in every case. This suggests two design changes: the summary carries the decision, so it should stay short, and the reason cards of multi-reason requests could be collapsed by default or reduced to one line each, since they largely repeat the summary. The Arabic summaries of the same requests are shorter in words (30 and 51), but no Arabic reading rate was assumed.

The KLM predicts the time of an expert who makes no errors; it does not measure understanding or trust. The estimate should therefore be confirmed with a small user study in which security practitioners decide on prepared requests on their own phones while their decision time is recorded, followed by Section D of the questionnaire in Appendix F (in particular D1, "I understood why the action was paused from the approval summary alone", and D2, "I could decide on the request in under 30 seconds").

### 4.2.9 Success criteria

@tab:success compares the measured results with the success criteria of the proposal (Section 1.3) and with the supporting requirement targets of Chapter 3.

Table: Success criteria, targets and measured results {#tab:success widths=1.9,1.2,2.1,0.8}
| Criterion | Target | Measured | Status |
|---|---|---|---|
| Interception of tool calls and results (MCP over stdio and HTTP, OpenAI-style function calling) | 100% of calls pass through the gateway | MCP proxy (stdio and streamable HTTP), OpenAI-compatible proxy and Guard API all route through `Gateway.execute` or `check_call`; {{reports/results_summary.json#python_tests.by_area.adapters}} adapter tests pass | Met (functional tests) |
| Declarative YAML policy with per-tool and per-parameter constraints and rate limits | Implemented and validated | All constraint operators, globs, rules, rate limits and monitor mode implemented; {{reports/results_summary.json#python_tests.by_area.policy}} policy tests pass | Met |
| Taint tracking blocks or escalates flows of untrusted or confidential data to external destinations | Rules fire on such flows, not on legitimate replies | Four taint rules implemented; {{reports/results_summary.json#python_tests.by_area.taint}} taint tests pass; no benign call denied | Met (functional); effect on attacks pending |
| Median added latency per tool call (NFR1) | ≤ 200 ms, judged on the sequential median and the separate-process layout | {{reports/results_summary.json#latency.separate_process.sequential_added_p50|.1f}} ms sequential; {{reports/results_summary.json#latency.separate_process.concurrent_added_p50|.0f}} ms with {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions (separate process). Context only: {{reports/results_summary.json#latency.in_process.concurrent_added_p50|.0f}} ms when client and server share one interpreter | Met (separate process) |
| Detector F1 on held-out English and Arabic test sets | ≥ 0.85 each | English {{reports/results_summary.json#detector.splits.test_en.f1|.3f}}; Arabic {{reports/results_summary.json#detector.splits.test_ar.f1|.3f}} | Pending data |
| Attack success reduction relative to the unprotected baseline | ≥ 80% | {{reports/results_summary.json#bench.scripted_attack_oracle.configs.full.asr_reduction|.1%}} | Pending data |
| Benign actions wrongly blocked | ≤ 5% | {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.fpr|.1%}} under full protection ({{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.calls}} benign calls per configuration, detector rules-only) | Met |
| Approval app, dashboard and tamper-evident audit log in which every blocked or approved action can be replayed | All decisions replayable | {{reports/results_summary.json#bench.scripted_benign_deny.replay_matched}} / {{reports/results_summary.json#bench.scripted_benign_deny.replay_checked}} and {{reports/results_summary.json#bench.scripted_benign_oracle.replay_matched}} / {{reports/results_summary.json#bench.scripted_benign_oracle.replay_checked}} decisions replayed identically; all chains verified | Met |
| NFR4: decision time on a phone | < 30 s | KLM estimate 21.9 s and 28.8 s reading the summary; 44.1 s reading every reason of a multi-reason request | Partially verified (user study pending) |
| NFR9: statement coverage of the core package | ≥ 80% | {{reports/results_summary.json#coverage.percent|.1f}}% | Met |
| NFR11: concurrent agent sessions on one node | ≥ 50 | {{reports/results_summary.json#latency.separate_process.sessions}} sessions, {{reports/results_summary.json#latency.separate_process.concurrent_errors}} errors | Met |
| NFR3: security testing of the gateway | Suite passes; no known vulnerable dependencies | {{reports/results_summary.json#python_tests.by_area.security}} STRIDE cases pass; Bandit {{reports/results_summary.json#security.bandit_issues}} issues; {{reports/results_summary.json#security.pip_audit_vulnerable}} vulnerable Python and {{reports/results_summary.json#security.npm_audit_vulnerabilities}} vulnerable npm packages | Met |
| NFR5: deployment with one `docker compose up` | Works | Not executed: Docker was not available on the build machine | Not verified (Docker unavailable) |

No criterion is shown as not met. The two most important outcomes of the proposal, detector F1 and the reduction of attack success, cannot be judged until the team's attack data exists; the decision-time target needs a user study; and the Docker deployment needs to be executed on a machine with Docker.

### 4.2.10 Limitations and threats to validity

**Results not yet available.** The detector has not been trained and no attack episode has been run, so the two headline claims of the project are untested. Until they are, the evaluation shows that Mirsad is cheap for legitimate work, not that it stops attacks. The benign false-positive rate and the detector's result false-positive rate were also measured with the rules-only detector and must be re-measured with the trained model, whose operating point is tuned for a false-positive rate of at most 5% on the validation split.

**Internal validity.** The scripted agent replays fixed plans, so the benign results show the effect of the gateway on correct behaviour but not how a real model's wording and tool choices interact with the policy; the LLM run has only {{reports/results_summary.json#bench.llm_smoke.tasks}} tasks. The oracle approver is an idealised human and the denying approver a pessimistic one; real approvers fall between them and can also approve a harmful request. The user tasks, the default policy and the escalation paths were written by the same team, which may favour low friction; for example, the policy deliberately escalates every external e-mail, and a different policy would give different numbers.

**External validity.** All results come from one simulated organisation with {{reports/results_summary.json#bench.scripted_benign_deny.tasks}} tasks, one local model, one laptop, SQLite and a single server worker. Real deployments have other tools, larger and noisier data, other languages and dialects, and more load. The concurrency results in particular should be repeated with several workers and PostgreSQL.

**Construct validity.** "False positive" counts only automatic denials; escalations are reported separately as friction, because a paused call costs a human's time but does not fail the task by itself. "Added latency" is measured against an in-process tool call and therefore includes HTTP handling that a direct remote tool call would also incur. The KLM estimate depends on assumed reading and opening times and on standard operator values defined for desktop input.

**Security evaluation.** The STRIDE suite tests the threats the team identified with inputs the team chose. It is not an independent penetration test, it does not include fuzzing of the API, and it does not model adaptive attackers who study the policy, the rules and the detector [@nasr2026attackermovessecond; @zhan2025adaptive]. Spotlighting and the detector are expected to be bypassed by such attackers; the policy and taint layers are the intended backstop, and their effect remains to be measured.

**Engineering limitations.** The gateway serialises decisions behind one lock, which limits throughput under concurrency. The Docker deployment has not been executed. The open integration items listed in Appendix B.6 (duplicate login throttling, the demonstration agent's embedded policy, the remaining literal direction marks in web files) are small but should be closed. The screenshots also show minor ordering defects where Latin names, times and Arabic text meet on one line (for example the version line of the Arabic Policies page and the requester line of the Arabic approval detail), which isolating those values in the markup would fix.

## 4.3 Individual and Group Contributions

The work was divided into the five workstreams of @tab:roles. @tab:i-tasks maps the main project tasks to the members who carried them out, following the workstream ownership and the task owners of the project plan (`docs/pm/plan.yaml`).

Table: Project Tasks & Task Assignments {#tab:i-tasks widths=1.5,3.2,1.8}
| TASK | DETAILS | ASSIGNED TEAM MEMBERS |
|---|---|---|
| PROJECT SETUP | Repository and branch rules, continuous-integration workflow, development environment (Python 3.12, Node.js, local Ollama model), Scrum board, engineering contract and shared data types | Abdulmalik bin Saedan (coordination, environment); Bader Alshuraie (engineering contract and shared types); all members (local setup) |
| PROJECT PROPOSAL | SPAP form: problem statement, objectives O1–O6, success criteria, initial plan and budget | All members, coordinated by Abdulmalik bin Saedan |
| REQUIREMENTS GATHERING AND ANALYSIS | Literature and product review; STRIDE threat model and attack taxonomy; functional and non-functional requirements, use cases and personas (SRS); benchmark and dataset design; stakeholder questionnaire | All members; threat model: Bader Abdullah Abbod Alyamini and Abdulmalik bin Saedan; benchmark and dataset design: Abdulmalik bin Saedan and Abdullah Naif Abdullah Al-Orabi |
| SYSTEM DESIGN | Architecture and high- and low-level design; policy-language specification; database and audit-chain design; detector and dataset design; wireframes of the dashboard and approver app | Bader Alshuraie (architecture, policy language); Bader Abdullah Abbod Alyamini (database, audit chain); Abdullah Naif Abdullah Al-Orabi (detector); Mohammed Yasser Alanssari (user interface) |
| DEVELOPMENT | Gateway pipeline, protocol adapters, SDK, policy engine, REST API and CLI; detector, rule base and dataset pipeline; taint tracker, audit log, redaction and storage; approval workflow; dashboard and approver PWA; demonstration workspace and agent; Mirsad-Bench | Bader Alshuraie; Abdullah Naif Abdullah Al-Orabi; Bader Abdullah Abbod Alyamini; Mohammed Yasser Alanssari; Abdulmalik bin Saedan (each for their workstream); approval workflow and admin API: Bader Alshuraie and Bader Abdullah Abbod Alyamini |
| TESTING & VALIDATION | Unit, integration and UI tests of each area; benchmark runs and latency measurement; detector evaluation; security testing of the gateway; integration checklist | All members (tests of their areas); Abdulmalik bin Saedan (benchmark, latency, security testing); Abdullah Naif Abdullah Al-Orabi (detector evaluation); Bader Abdullah Abbod Alyamini and Mohammed Yasser Alanssari (security testing) |
| DEPLOYMENT | Docker image and Compose file (gateway and PostgreSQL), setup and demo scripts, production web build, installation and user guide | Mohammed Yasser Alanssari and Bader Alshuraie (deployment, user guide); Abdulmalik bin Saedan (demo and evidence scripts) |
| FINAL REPORT & PRESENTATION | Report chapters, figures, poster, slides and open-source release | All members, coordinated by Abdulmalik bin Saedan |

**Bader Alshuraie (SE)** owned the core of the gateway: the decision pipeline in `gateway.py`, the policy language with its schema, validator and engine, the rate limiter and the protection against unsafe regular expressions, the protocol adapters (upstream manager, MCP proxy over stdio and HTTP, OpenAI-compatible proxy), the Python SDK, the REST API and the command line. Alshuraie was also responsible for the architecture and the policy-language specification that the other workstreams coded against. The policy, adapter and API areas account for {{reports/results_summary.json#python_tests.by_area.policy}}, {{reports/results_summary.json#python_tests.by_area.adapters}} and {{reports/results_summary.json#python_tests.by_area.api}} tests respectively.

**Abdullah Naif Abdullah Al-Orabi (SE, AI and DS)** owned the Arabic and English injection detector: the normalisation with its offset map and evasion signals, language identification including Arabizi, the YAML rule base and its matcher, the hashed n-gram model with sliding windows, the noisy-OR ensemble and its calibration, pickle-free model persistence, sanitising and spotlighting, and the dataset pipeline with group splitting, train-only augmentation and leakage checks. Al-Orabi was also responsible for the dataset schema and labelling guideline that the team's data must follow. The detector area has {{reports/results_summary.json#python_tests.by_area.detector}} tests, none of which contains adversarial text.

**Bader Abdullah Abbod Alyamini (IS, CYS)** owned the taint tracker (value extraction, session store, the four rules and minimal snapshots for replay) and the audit layer: the HMAC hash chain with verification and external anchors, redaction of secrets and personal identifiers, query and export, the database schema and storage layer, and the authentication primitives. Alyamini contributed to the threat model, the approval workflow and the security testing. The taint and audit areas have {{reports/results_summary.json#python_tests.by_area.taint}} and {{reports/results_summary.json#python_tests.by_area.audit}} tests.

**Mohammed Yasser Alanssari (IS, CYS)** owned the two web front ends: the bilingual, accessible administration dashboard with its ten pages and the installable approver PWA with its service worker, Web Push, deep links, confirmation flow and offline shell, together with the shared live-event client and the English and Arabic dictionaries. Alanssari also owned the user-facing side of the approval workflow, contributed to the security testing and to the deployment and user guide. The web code has {{reports/results_summary.json#web_tests.total}} tests, including contrast and dictionary-consistency checks.

**Abdulmalik bin Saedan (IS, CYS)** managed the project (plan, sprints, coordination and integration checklist) and owned the simulated Najd Trading Co. workspace with its MCP server, the demonstration agent and Demo console scenarios, Mirsad-Bench with its scenarios, defence configurations, metrics and latency benchmark, the security test suite of the gateway and the evidence scripts that produce the numbers in this chapter. The benchmark, demonstration and security areas have {{reports/results_summary.json#python_tests.by_area.bench}}, {{reports/results_summary.json#python_tests.by_area.demo}} and {{reports/results_summary.json#python_tests.by_area.security}} tests.

**All members** took part in the literature review, the requirements, the design reviews, code review and integration, and the report, poster and presentation. As disclosed in Section 3.6.6, an AI coding assistant was used across the workstreams; here, owning an area means that the member designed, reviewed, tested and integrated its code, can explain it, and is accountable for it.
