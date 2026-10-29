# Mirsad gateway, REST API and CLI

**Area:** api (owner: Bader Alshuraie). **Code:** `src/mirsad/gateway.py`, `src/mirsad/api/`, `src/mirsad/cli.py`. **Tests:** `tests/api/`.

This document describes the part of Mirsad (مرصاد) that connects the security layers to the outside world:

1. **The gateway pipeline** (`mirsad.gateway.Gateway`): the decision engine that every tool call and every tool result passes through.
2. **The HTTP API** (`mirsad.api.create_app`): the agent-facing endpoints (Guard API, tool invocation, OpenAI-compatible proxy, MCP), the management API used by the dashboard and the approver PWA, live updates over Server-Sent Events, and static hosting of the web apps.
3. **The command-line tool** (`mirsad`): it runs the server, bootstraps users, and manages policies, the audit log and the detector.

---

## 1. The gateway pipeline

### 1.1 Purpose

An LLM agent that reads untrusted content (e-mails, web pages, documents, CRM notes) can be hijacked by instructions hidden in that content (*indirect prompt injection*). Mirsad does not try to make the model itself robust. It enforces security **outside** the model, at the only place where an attack turns into damage: the tool call.

```
            check_call                                   inspect_result
ToolCall ──► Policy ─► RateLimit ─► Taint ─► combine ─► Approval? ──► tool runs ──► Detector ─► Sanitize/Spotlight ─► Taint register ──► agent
                 │          │          │         │            │                         │               │                  │
                 └──────────┴──────────┴─────────┴────────────┴── audit (HMAC hash chain) ┴───────────────┴──────────────────┘
```

### 1.2 Public interface

```python
Executor = Callable[[ToolCall], Awaitable[ToolResult]]

class Gateway:
    def __init__(self, *, policy, taint, detector, audit, approvals,
                 agent_names: dict[str, str] | None = None,
                 policy_store: Callable[[str], str | None] | None = None,   # version -> YAML (replay)
                 max_result_chars: int = 200_000,          # extension: results are truncated to this size
                 audit_content_chars: int = 8_000,         # extension: result text kept in the audit log
                 executor_timeout_s: float | None = 120.0, # extension: tool execution timeout
                 sanitizer=None, spotlighter=None)         # extension: defaults to mirsad.detector.{sanitize,spotlight}
    policy: PolicyEngine                       # property; assigning it calls set_policy()
    def set_policy(self, engine) -> None       # atomic hot swap
    async def check_call(self, call, *, wait_for_approval=True) -> Decision
    async def inspect_result(self, result) -> InspectionOutcome
    async def execute(self, call, executor) -> GatewayResponse
    def replay(self, seq: int) -> ReplayReport  # KeyError if missing, ReplayError if not replayable
    def is_waiting_for(self, approval_id) -> bool

class ReplayReport(BaseModel):
    seq: int; event_type: str; original_action: str | None; replayed_action: str | None
    match: bool; details: dict
```

The module also exports `principal_var`, a context variable that holds the authenticated credential, and `explain_decision(decision)`, a one-line bilingual explanation of a block.

### 1.3 `check_call`: deciding on a tool call

1. Take a snapshot of the session's taint state. Then call `policy.evaluate_call(call, session_tainted=...)`, which applies allow-lists, argument constraints, rate limits, global rules and the tool's risk.
2. If the agent is known and taint tracking is enabled, call `taint.evaluate_call(call, profile, sink, settings)`. This checks, for example, whether untrusted content is flowing to an external sink, or whether a destination came from untrusted text.
3. `combine_reasons` (deny-overrides): the most severe action wins, and the risk score is the maximum over all reasons.
4. If the result is ALLOW but `policy.approval_required(profile, risk, taint_fired)` is true, the action becomes REQUIRE_APPROVAL (reason `APPROVAL_POLICY`).
5. Write a `tool_call.decision` audit event with payload `{call, profile, sink, reasons, snapshot, rate_counts, risk_score, enforced, returned_action, latency_ms, principal}`. The stored snapshot is the **minimal snapshot** from the taint tracker: only the values the rules looked at. This keeps events small and replay exact.
6. If the action is REQUIRE_APPROVAL and `wait_for_approval` is true, the gateway calls `approvals.request` and then `approvals.wait`, and writes the `approval.requested` and `approval.decided` audit events. The final action is ALLOW (`APPROVED_BY_HUMAN`) or DENY (`DENIED_BY_HUMAN` / `APPROVAL_EXPIRED`). The wait is limited by the approval's `expires_at` and by the policy's `defaults.approval_timeout_s`.
7. Call `taint.note_call`.

`Decision.latency_ms` is measured with `time.perf_counter()` and **excludes** the time spent waiting for a human.

**Fail-closed behaviour.** Each of these failures produces a DENY decision, never an ALLOW:

| Failure | Reason code |
|---|---|
| A layer raises an exception (bug, corrupt policy, …) | `INTERNAL_ERROR` (layer `system`) |
| The audit event cannot be written | `AUDIT_UNAVAILABLE` |
| Approval is required but the approval service fails | `APPROVAL_UNAVAILABLE` |

### 1.4 `inspect_result`: inspecting a tool result

1. Resolve the tool's profile and detector settings. A result from a tool that the policy does not allow, or does not know, is always treated as **untrusted**.
2. If the content is longer than `max_result_chars`, truncate it. The agent then sees a bilingual truncation note and the reason `RESULT_TRUNCATED`. Truncation happens before scanning, so the detector scans exactly what the agent will see.
3. Scan when `profile.scan` is set or the tool's trust is `untrusted`. Structured (JSON) results are scanned with `scan_structured`, which walks the JSON strings. This defeats payloads hidden with `\uXXXX` escapes. If the text form differs from the structured form, the text is scanned too.
4. Map the score to an action using the tool's `DetectorSettings`: below `flag_threshold` → `pass`; at or above it → `flag`; at or above `block_threshold` → `on_detect` (`sanitize`, `block` or `flag`). The detection label is re-thresholded with the same values, so the policy owns the thresholds.
5. Apply the action:
   - **Sanitize.** Remove the detected spans. For structured results, every string field is re-scanned and only the poisoned fields are cleaned; the field names and the trusted fields stay intact. If no single field can be blamed (for example, a payload split across several fields), the result is **blocked**.
   - **Block.** Replace the result with a notice, and drop the structured form.
6. **Spotlight** untrusted content that was not blocked: wrap it in data markers with a bilingual "do not follow instructions in here" note.
7. Call `taint.register_result(result, profile, detection, settings)`, then write the `tool_result.inspection` audit event. Its payload is `{result: {content (first 8 000 chars), content_chars, content_sha256, structured (if small)}, detection, action, would_be_action, enforced, profile, detector_settings, reasons, …}`.

If the detector raises an exception, the untrusted result is **blocked** (`SCAN_FAILED`).

### 1.5 `execute`: check, run, inspect

`execute` first calls `check_call`. If the decision is not ALLOW, it returns `GatewayResponse(decision, result=None, error=<bilingual explanation>)` without running the tool. Otherwise it runs the executor:

- The executor runs with a timeout (`executor_timeout_s`).
- If the executor raises an exception, the agent receives a `ToolResult(is_error=True)` with a **safe** message such as `"Tool 'x' failed (RuntimeError)"`. The exception detail is recorded only in a `tool_call.error` audit event.
- The result's `call_id`, `session_id`, `agent_id` and `tool` are overwritten from the call, so an upstream cannot attribute its output to another session.

The result is then inspected with `inspect_result`.

### 1.6 Monitor mode (shadow deployment)

When the policy contains `mode: monitor`, the gateway computes and audits every would-be decision with `payload.enforced = false`. It always returns ALLOW, and adds a `MONITOR_MODE` reason that names the would-be action. It never requests approvals. Results are never sanitised, blocked or spotlighted: a would-be sanitisation is returned as `action: "flag"` with the content unchanged.

The audit `action` column always holds the **would-be** action, so the dashboard statistics show what enforcement *would* have done. Operators use this to tune a policy before enforcing it.

### 1.7 Deterministic replay

`replay(seq)` re-evaluates a stored event:

- **`tool_call.decision` events.** The gateway loads the policy version recorded in the event: from the policy store, through a cache of up to 8 engines. It rebuilds the `ToolCall` and the stored minimal taint snapshot, then re-runs the policy (passing the stored `rate_counts`, so the live rate limiter is not touched) and the taint tracker (passing the stored snapshot, so the evaluation is a pure function of its inputs). It then compares the actions and the reason codes.
- **`tool_result.inspection` events.** The gateway re-scans the stored content with the recorded version's detector settings and compares the inspection actions.

`details` lists the reason codes that were added or removed, the original and replayed risk scores, and `notes` that explain any cause of divergence. Those causes are: arguments redacted by the audit log, payloads truncated to the audit size limit, or only part of a long result having been stored.

### 1.8 Concurrency

- Synchronous work (policy, taint, audit writes, detector scans) runs in worker threads (`asyncio.to_thread`), so a slow SQLite commit or a long scan does not stall the event loop or the SSE streams.
- One re-entrant lock makes this sequence atomic: *snapshot → evaluate → audit*, and *register → audit*. Taint state and audit order therefore stay consistent under concurrent calls. A test runs 60 concurrent calls and then checks that the hash chain still verifies.
- `set_policy` swaps the engine atomically. An evaluation that has already started keeps the engine it began with, so a single decision never mixes two policy versions.

---

## 2. HTTP API

`create_app(settings=None, *, gateway_overrides=None, static_dir=None) -> FastAPI`

On startup the factory builds `Database`, `AuditLog` (the HMAC key is derived from the secret with `audit_key_from_secret`), `Notifier`, `ApprovalService`, `PolicyEngine` (the active DB version; otherwise `settings.policy_path`, stored as the first version; otherwise a built-in deny-all policy), `TaintTracker`, `InjectionDetector`, `UpstreamManager` (from `settings.upstreams_path`; when that file does not exist the manager is empty, except in demo mode, where the in-process demo workspace `demo.workspace_server:server` is used so that `/v1/tools`, `/mcp` and the Demo Console share one simulated world) and `Gateway`.

These are stored on `app.state` as `settings, db, audit, notifier, approvals, policy_store, taint, detector, upstreams, gateway`. `app.state.components` holds the complete object graph.

`api/deps.py` provides the FastAPI dependencies `get_gateway(request)`, `require_agent` (returns `mirsad.auth.AgentInfo`) and `require_user(*roles)` (returns `mirsad.auth.UserInfo`).

`gateway_overrides` replaces any of `db, audit, notifier, approvals, policy, policy_store, taint, detector, upstreams, gateway, auth, policy_module, sanitizer, spotlighter`. Tests and benchmarks use it to plug in their own components; an unknown key raises `ValueError`.

**Lifespan (startup and shutdown).**

At startup the app:
- starts the upstream tool servers;
- registers an audit listener that relays every new audit event to the notifier, which feeds SSE `audit.event`;
- writes a `system.started` audit event;
- runs a maintenance task every 5 s. The task expires overdue approvals and **hot-swaps the policy if another process activated a new version**, for example `mirsad policy activate`.

At shutdown it closes the MCP sessions, the upstreams and any pending Web Push deliveries.

### 2.1 Authentication model

| Principal | Credential | Where it is accepted |
|---|---|---|
| Human user (`admin`, `approver`, `auditor`) | `Authorization: Bearer <JWT>` from `POST /api/auth/login` (HS256, `token_ttl_hours`, default 12 h) | `/api/*` |
| Agent | `Authorization: Bearer mk_<prefix>_<secret>` or `X-Mirsad-Key: mk_...` | `/v1/*`, `/mcp` |

- The user is reloaded on every request, so disabling a user or changing their role takes effect immediately.
- Agent keys are rejected on `/api/*` and user JWTs are rejected on `/v1/*`.
- The policy agent used for evaluation is the agent's `policy_agent_id`. The credential's id is recorded as `principal` in the audit payloads.
- **Login throttling.** After 5 failed attempts per username+IP within 5 minutes, and after 30 failed attempts per IP within 5 minutes, the server answers `429` with `Retry-After`. Every failure is audited as `auth.login_failed` (the username is stored, the password never is). Successful logins are audited as `auth.login`.

**Roles**

| Area | admin | approver | auditor |
|---|:-:|:-:|:-:|
| Approvals (list, decide) | ✔ | ✔ | |
| Audit (search, verify, replay, export), policies (read), tools | ✔ | | ✔ |
| Policies (validate, activate), agents, users | ✔ | | |
| `/api/auth/me`, stats, detector playground, SSE stream, push, demo | ✔ | ✔ | ✔ |

### 2.2 Errors

Every error is JSON with a string `detail`:

| Status | Meaning |
|---|---|
| 400 | Event cannot be replayed, or the OpenAI proxy rejected the request (e.g. `stream=true`) |
| 401 | Missing, invalid or expired credential (`WWW-Authenticate: Bearer`) |
| 403 | Authenticated, but the role is not allowed |
| 404 | Unknown resource |
| 409 | Conflict: approval already decided or expired, duplicate user or agent, last active admin |
| 413 | Request body larger than 1 MB |
| 422 | Validation error. `detail` is a readable string and `errors` is `[{loc, msg, type}]`. **Submitted values are never echoed back.** |
| 429 | Login throttled (`Retry-After` header) |
| 500 | `{"detail": "Internal server error"}`. Details are logged, never returned. |
| 502 / 503 | Demo LLM unavailable / no upstream tool runtime configured |

### 2.3 Security hardening

- Every response carries `Content-Security-Policy` (`default-src 'self'`, `script-src 'self'`, `frame-ancestors 'none'`, …), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin` and `Permissions-Policy`.
- `/api`, `/v1` and `/mcp` responses also carry `Cache-Control: no-store`.
- HSTS is added over HTTPS.
- `/docs` and `/redoc` get a separate CSP that allows the Swagger UI and ReDoc CDN assets.
- Requests larger than 1 MB are rejected with 413. This applies both to a declared `Content-Length` and to chunked bodies, which are counted as they stream.
- CORS is allowed only for `settings.cors_origins`. Credentials mode is not used, because tokens travel in headers.
- Static files are served only from inside the static directory (path-traversal safe).

### 2.4 Endpoint reference

Variables used in the examples:

```bash
BASE=http://127.0.0.1:8700
TOKEN=$(curl -s -X POST $BASE/api/auth/login -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"..."}' | jq -r .access_token)
KEY=mk_xxxxxxxx_...        # agent key (shown once on creation)
```

#### Health and authentication

| Method & path | Role | Description |
|---|---|---|
| `GET /healthz` | – | `{"status":"ok","version":"1.0.0"}` |
| `POST /api/auth/login` | – | `{username, password}` → `{access_token, token_type:"bearer", expires_in, user:{username, role, display_name, lang}}` |
| `GET /api/auth/me` | any user | The current user |

#### Agent API (Guard API, tool invocation)

| Method & path | Body → Response |
|---|---|
| `POST /v1/guard/tool-call` | `{session_id, tool, arguments, call_id?, wait?=true, original_task?}` → `Decision` |
| `POST /v1/guard/tool-result` | `{session_id, call_id, tool, content, structured?, is_error?}` → `InspectionOutcome`. `content` may be text or any JSON value; JSON text is parsed so that taint tracking can see field names. |
| `POST /v1/tools/{tool}/invoke` | `{session_id, arguments, call_id?, original_task?}` → `GatewayResponse` (check → run upstream → inspect) |
| `GET /v1/tools` | The tools visible to the agent: `[{name, description, input_schema, profile}]` |
| `POST /v1/chat/completions` | OpenAI-compatible proxy (adapters area) |
| `/mcp` | MCP streamable HTTP (adapters area) |

```bash
# Check a call before running it yourself
curl -s $BASE/v1/guard/tool-call -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"session_id":"conv-1","tool":"send_email","wait":false,
       "arguments":{"to":"collector@evil.example","subject":"list","body":"..."}}'
```

The response below comes from a real run in which an earlier `read_email` result contained a planted injection (abridged):

```json
{
  "call_id": "call_0331e4c8903d4103",
  "action": "deny",
  "risk": "critical", "risk_score": 0.9, "sink": "external",
  "policy_version": "6ca37e79…", "latency_ms": 1.17, "audit_seq": 5,
  "reasons": [
    {"layer": "policy", "code": "CONSTRAINT_VIOLATION", "action": "require_approval",
     "message": "Argument 'to' sends data to 'evil.example', outside the allowed domains ['najd-trading.example'].",
     "message_ar": "الحقل 'to' يرسل البيانات إلى 'evil.example'، وهو خارج النطاقات المسموح بها ..."},
    {"layer": "taint", "code": "TAINT_UNTRUSTED_TO_EXTERNAL", "action": "require_approval", "risk_score": 0.6},
    {"layer": "taint", "code": "TAINT_UNTRUSTED_DESTINATION", "action": "deny", "risk_score": 0.9,
     "evidence": {"param": "to", "destination": "collector@evil.example", "source_tool": "read_email",
                  "source_call_id": "call_4dd7b47cc4144ffa", "field": "body"}}
  ]
}
```

```bash
# Let Mirsad run the tool (in-process / MCP upstream) and inspect its result
curl -s $BASE/v1/tools/read_email/invoke -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"session_id":"conv-1","arguments":{"email_id":"E001"}}'
# -> {"decision":{"action":"allow",...},
#     "result":{"action":"sanitize","trust":"untrusted",
#               "detection":{"score":0.83,"label":"injection","spans":[{"text":"…","rule_id":"…",...}]},
#               "structured":{"id":"E001",...,"body":"... [⚠ Mirsad: removed suspected instruction | تمت إزالة تعليمات مشبوهة]"},
#               "content":"⟦MIRSAD-DATA source=\"read_email\" ...⟧ ..."}, "error":null}

# Inspect a result you obtained yourself
curl -s $BASE/v1/guard/tool-result -H "X-Mirsad-Key: $KEY" -H 'Content-Type: application/json' \
  -d '{"session_id":"conv-1","call_id":"c-7","tool":"fetch_url","content":"<html>…</html>"}'
```

With `wait: true` (the default), a call that needs approval keeps the HTTP request open until an approver decides or the approval expires (`approval_timeout_s`, default 120 s). Set your client timeout accordingly; the SDK defaults to 150 s. With `wait: false` the call returns `require_approval` immediately and no approval request is created. Treat that result as "not allowed".

#### Approvals (approver / admin)

| Method & path | Body → Response |
|---|---|
| `GET /api/approvals?status=pending&limit=100` | `[ApprovalRecord]`, newest first. `status` is one of `pending, approved, denied, expired, cancelled`; omitted or empty (`status=`) means any status. |
| `GET /api/approvals/{id}` | `ApprovalRecord` (includes `summary_en` / `summary_ar`) |
| `POST /api/approvals/{id}/decision` | `{approve: bool, note?}` → `ApprovalRecord`. 409 if already decided or expired. |

```bash
curl -s -X POST $BASE/api/approvals/apr_123/decision -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"approve": false, "note": "unknown recipient"}'
```

When a gateway call is waiting on the approval, the gateway writes `approval.decided`. When nobody is waiting (an orphaned approval, for example after a restart), the API writes it with `source: "api"`. Each decision is audited exactly once.

#### Live stream (any user)

`GET /api/stream` returns `text/event-stream`. It requires the `Authorization` header; query-string tokens are not accepted. Events:

| Event | Data |
|---|---|
| `ready` | `{user, role}`, sent once the subscription is registered |
| `approval.requested` / `approval.decided` | `ApprovalRecord` |
| `audit.event` | `AuditEvent`. Approvers receive only `{seq, ts, event_type, tool, action, risk}`, because the audit payload requires the admin or auditor role. |

A heartbeat comment line (`: ping`) is sent every 15 s.

```bash
curl -N $BASE/api/stream -H "Authorization: Bearer $TOKEN"
```

#### Web Push (any user)

| Method & path | Description |
|---|---|
| `GET /api/push/vapid` | `{public_key, enabled}` |
| `POST /api/push/subscribe` | Browser `PushSubscription.toJSON()` → 204. Only `https://` endpoints are accepted. |
| `POST /api/push/unsubscribe` | `{endpoint}` → 204 |

Delivery is handled by the approval service. It pushes `approval.requested` to admins and approvers when VAPID keys are configured.

#### Audit (admin / auditor)

| Method & path | Description |
|---|---|
| `GET /api/audit/events?agent_id&tool&action&event_type&session_id&call_id&since&until&q&limit&offset&order` | `{items:[AuditEvent], total}`. `since` and `until` are epoch seconds; `q` is free text. |
| `GET /api/audit/events/{seq}` | One event |
| `POST /api/audit/verify` | `AuditVerifyReport` (`ok, checked, head_seq, head_hash, first_bad_seq, message`). Also written to the log as `audit.verified`. |
| `POST /api/audit/events/{seq}/replay` | `ReplayReport` (404 if missing, 400 if the event type cannot be replayed) |
| `GET /api/audit/export?format=json\|csv&…filters` | File download. JSON keeps the chain fields for offline verification. |

```bash
curl -s -X POST $BASE/api/audit/events/5/replay -H "Authorization: Bearer $TOKEN"
# {"seq":5,"event_type":"tool_call.decision","original_action":"deny","replayed_action":"deny","match":true,
#  "details":{"original_reasons":["TOOL_RISK","CONSTRAINT_VIOLATION","TAINT_UNTRUSTED_TO_EXTERNAL",
#             "TAINT_UNTRUSTED_DESTINATION"],"reasons_match":true,"notes":[],...}}
curl -s "$BASE/api/audit/export?format=csv&action=deny" -H "Authorization: Bearer $TOKEN" -o denied.csv
```

#### Statistics (any user)

`GET /api/stats/overview?hours=24` returns:

```json
{"hours":24.0,"total_calls":2,"allowed":1,"denied":1,"approvals_required":0,"approvals_pending":0,
 "injections_detected":1,"results_sanitized":1,"results_blocked":0,"results_inspected":1,
 "median_latency_ms":0.225,"p95_latency_ms":0.229,"audit_ok":true,"audit_head_seq":5,
 "by_tool":[{"tool":"send_email","allowed":0,"denied":1,"approval":0}],
 "by_layer":[{"layer":"policy","count":1},{"layer":"taint","count":1},{"layer":"detector","count":1}]}
```

`GET /api/stats/timeseries?hours=24&bucket_minutes=60` returns `[{t, allowed, denied, require_approval, injections}]`, where `t` is the start of the bucket in epoch seconds. Buckets are aligned to `bucket_minutes`, and empty buckets are included.

How the figures are computed:

- Counts are SQL aggregations over the indexed columns of `audit_events`.
- Latency, `by_layer` and injection counts are read from the JSON payload. On SQLite this uses JSON1 (`json_extract` / `json_each`); on other databases the payloads are parsed in Python.
- `by_layer` is the number of calls that each layer objected to (reasons whose action is not `allow`), plus inspections that the detector flagged.
- Latency is the in-gateway decision time recorded in the decision event. It excludes the audit write and any human wait.
- `audit_ok` comes from a full chain verification, cached for 30 s while the head of the chain has not moved.
- The call counts come from `tool_call.decision` events, whose action is the gateway's decision *before* any human was involved. A call that needed approval is counted in `approvals_required` (and in `by_tool[].approval`) whether the approver later allowed or denied it; the human outcome is in the `approval.decided` events.

#### Policies

| Method & path | Role | Description |
|---|---|---|
| `GET /api/policies` | admin, auditor | `{active:{version, yaml_text, created_at, created_by, active, comment}, versions:[…]}` |
| `GET /api/policies/{version}` | admin, auditor | One version with its YAML |
| `POST /api/policies/validate` | admin | `{yaml_text}` → `{valid, errors:[str]}` |
| `PUT /api/policies` | admin | `{yaml_text, comment?}` → the activated version, plus `previous_version`, `mode` and `agents`. **Hot-reloads the gateway** and writes `policy.activated`. 422 if invalid. |
| `POST /api/policies/{version}/activate` | admin | Re-activate a stored version (rollback) |

Versions are content-addressed: the version string is the engine's SHA-256. Rate-limit counters carry over across a hot reload, so editing the policy does not reset limits.

```bash
curl -s -X PUT $BASE/api/policies -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  --data-binary @<(jq -Rs '{yaml_text: ., comment: "tighten send_email"}' configs/policies/default.yaml)
```

#### Agents and users (admin)

| Method & path | Description |
|---|---|
| `GET /api/agents` | `[{id, name, description, policy_agent_id, key_prefix, created_at, disabled, last_seen_at}]` |
| `POST /api/agents` | `{id (slug), name, policy_agent_id, description?}` → 201 `{agent, api_key, warnings}`. **The key is shown only once.** `warnings` notes a `policy_agent_id` that is missing from the active policy. |
| `POST /api/agents/{id}/rotate-key` | `{agent, api_key}`. The old key stops working immediately. |
| `PATCH /api/agents/{id}` | `{name?, description?, policy_agent_id?, disabled?}` |
| `DELETE /api/agents/{id}` | 204 |
| `GET /api/users` | `[{username, role, display_name, lang, created_at, disabled}]`. Password hashes are never returned. |
| `POST /api/users` | `{username, role, password?, display_name?, lang?}` → 201 `{user, generated_password?}`. When the password is omitted, a strong one is generated and returned **once**. |
| `PATCH /api/users/{username}` | `{role?, display_name?, lang?, disabled?, password?}` |
| `DELETE /api/users/{username}` | 204. You cannot delete yourself or demote, disable or delete the last active admin (409). |

All of these changes are audited (`agent.created`, `agent.key_rotated`, `agent.updated`, `agent.deleted`, `user.created`, `user.updated`, `user.deleted`). Keys and passwords are never written to the audit log.

#### Tools (admin / auditor)

`GET /api/tools` returns `[{name, description, upstream, input_schema, profiles:{<policy agent id>: ToolProfile}}]`.

#### Detector playground (any user)

`POST /api/detector/scan` `{text}` (max 100 000 characters) → `DetectionResult`.

#### Demo Console (any user; only when `MIRSAD_ENABLE_DEMO=true`)

| Method & path | Description |
|---|---|
| `POST /api/demo/chat` | `{message, session_id?, protected=true, lang?}` → `{reply, session_id, protected, stopped_reason, steps:[{tool, arguments, decision?, result_preview, inspection?, blocked}], attacker_inbox:[…]}` |
| `GET /api/demo/state` | `{world: World.snapshot(), attacker_inbox}` |
| `POST /api/demo/reset` | Reset the simulated workspace and the demo taint sessions |
| `GET /api/demo/scenarios` | Curated attack scenarios (`demo.scenarios`) |
| `POST /api/demo/scenarios/{id}/apply` | Reset the world and plant the scenario's payloads. This endpoint is an extension, used by the Demo Console's "load attack" button. |

- `protected=true` runs `demo.agent.DemoAgent` with `GatewayBackend` on this app's gateway (policy agent `email-crm-assistant`). `protected=false` uses `DirectBackend`.
- `attacker_inbox` lists the world's outbox e-mails and `http_log` requests that go to non-internal domains.
- Demo runs are serialised, because there is one simulated world.
- The LLM is `settings.llm_base_url` / `llm_model` (Ollama `qwen2.5:7b` by default). If it is unreachable the endpoint returns 502.

#### Static web apps

| Path | Served file |
|---|---|
| `/` and any client route | `static/index.html` (dashboard) |
| `/approve`, `/approve/*` | `static/approve.html` (approver PWA) |
| `/assets/*` | Vite build output |
| Other root files (`sw.js`, `manifest.webmanifest`, icons) | Served if present |

A missing file with an extension returns 404. If the web app has not been built, `/` returns a JSON note that explains how to build it. The OpenAPI UI is at `/docs` (ReDoc at `/redoc`, schema at `/openapi.json`).

---

## 3. Integration guides

Mirsad supports three ways of putting the firewall in front of an agent. All three run the same gateway pipeline and write to the same audit log.

### 3.1 Guard API (any framework, any language)

Use this style when you keep executing tools yourself. Call `check_call` before running a tool and `inspect_result` after it:

```python
import httpx
H = {"Authorization": f"Bearer {KEY}"}
d = httpx.post(f"{BASE}/v1/guard/tool-call", headers=H, timeout=150,
               json={"session_id": sid, "tool": name, "arguments": args, "call_id": cid}).json()
if d["action"] != "allow":
    tool_output = f"Blocked by Mirsad: {d['reasons'][-1]['message']}"
else:
    raw = run_my_tool(name, args)
    out = httpx.post(f"{BASE}/v1/guard/tool-result", headers=H,
                     json={"session_id": sid, "call_id": cid, "tool": name, "content": raw}).json()
    tool_output = out["content"]          # sanitised + spotlighted text to give back to the model
```

Alternatively, let Mirsad run the tool for you with `POST /v1/tools/{tool}/invoke`, or use the Python SDK (`mirsad.sdk.MirsadClient`, adapters area), which wraps these calls (`check_call`, `inspect_result`, `invoke`, and the `@guard` decorator).

**Use one `session_id` per conversation.** Taint tracking is per session: content read in one session influences decisions in that same session.

### 3.2 OpenAI-compatible proxy (no agent code change)

Point the agent's OpenAI client at Mirsad and use the agent key as the API key:

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8700/v1", api_key=KEY,
                default_headers={"X-Mirsad-Session": "conv-42"})
```

Mirsad forwards the request to `settings.llm_base_url` (`MIRSAD_LLM_BASE_URL`, e.g. Ollama). Every `role: tool` message is inspected and sanitised before it reaches the model, and every `tool_calls[i]` that the model returns is checked. Denied calls are removed and replaced by an explanatory assistant text. Only non-streaming requests are supported; `stream=true` returns 400. See the adapters documentation for details.

### 3.3 MCP proxy (MCP hosts such as Claude Desktop or IDE agents)

**Streamable HTTP.** Configure the MCP server URL as `http://127.0.0.1:8700/mcp` and send `Authorization: Bearer mk_...`. You can optionally set `X-Mirsad-Session`. The agent sees only the upstream tools its policy allows, and every `call_tool` runs through `gateway.execute`. A denied call comes back as an MCP tool error whose text explains the block in English and Arabic.

**stdio** (the host launches a process):

```json
{"mcpServers": {"najd-workspace": {"command": "mirsad",
  "args": ["mcp-proxy", "--url", "http://127.0.0.1:8700"],
  "env": {"MIRSAD_AGENT_KEY": "mk_..."}}}}
```

Upstream tool servers are configured in `configs/upstreams.yaml` (`MIRSAD_UPSTREAMS_PATH`). Supported transports are `inprocess`, `stdio` and `http`. If the file does not exist, the server starts without upstream tools, or, with `MIRSAD_ENABLE_DEMO=true`, with the in-process demo workspace (the same entry as the spec example: `{name: workspace, transport: inprocess, target: demo.workspace_server:server}`). An existing file always wins.

---

## 4. Command line

```
mirsad [--data-dir DIR] [--log-level LEVEL] COMMAND
python -m mirsad.cli ...        # same commands without the console script
```

| Command | Description |
|---|---|
| `serve [--host] [--port] [--demo/--no-demo]` | Run the gateway, API and web apps (uvicorn) |
| `init [--demo] [--admin-password PW]` | Create the DB, store the initial policy version, and create the `admin`, `approver` and `auditor` users. With `--demo`, also create agent `demo-agent` (policy agent `email-crm-assistant`). Generated credentials are appended to `<data_dir>/credentials.txt` (mode **600**), and **only the file path is printed**. The admin password can also come from `MIRSAD_ADMIN_PASSWORD`. Running `init` again only creates what is missing. |
| `policy validate FILE` | Exit code 1 and the error lines if the policy is invalid |
| `policy activate FILE [--comment]` | Store and activate a version. A running server picks it up within about 5 s. Audited. |
| `audit verify` | Print the verification report; exit code 1 if the chain is broken |
| `audit export --format json\|csv [--out FILE] [--agent-id --tool --action --event-type --since --until]` | Export audit events |
| `audit replay SEQ` | Print the `ReplayReport` |
| `scan TEXT` / `scan --file PATH` | Print the `DetectionResult` |
| `agent create NAME --policy-agent ID [--id SLUG] [--description] [--key-file PATH]` | Print the key once, or write it to a mode-600 file |
| `user create USERNAME --role R [--password] [--display-name] [--lang en\|ar]` | The password is prompted (hidden, with confirmation) when omitted |
| `mcp-proxy --agent-key KEY [--url] [--session-id]` | stdio MCP server that forwards to a running gateway (`MIRSAD_AGENT_KEY` is accepted) |
| `detector train [ARGS…]` | Delegates to `python -m mirsad.detector.train ARGS…` |

Typical first run:

```bash
mirsad init --demo                 # -> Credentials written to /…/.mirsad/credentials.txt (mode 600).
mirsad serve --demo                # http://127.0.0.1:8700  (dashboard /, approver /approve, docs /docs)
                                   # (or MIRSAD_ENABLE_DEMO=true mirsad serve)
```

With the demo enabled and no `configs/upstreams.yaml`, the twelve demo workspace tools are served in-process, so the `demo-agent` key from `credentials.txt` can call `GET /v1/tools` and `POST /v1/tools/{tool}/invoke` right away.

Logging goes to stderr. Generated secrets are never logged.

## 5. Configuration

All settings are environment variables with the `MIRSAD_` prefix, or entries in `.env` (see `mirsad.config.Settings`). The ones that matter for this area are:

| Variable | Default | Effect |
|---|---|---|
| `MIRSAD_HOST`, `MIRSAD_PORT` | `127.0.0.1`, `8700` | Bind address |
| `MIRSAD_DATA_DIR` | `.mirsad` | SQLite DB, `secret.key`, `credentials.txt` |
| `MIRSAD_DATABASE_URL` | SQLite in `DATA_DIR` | Any SQLAlchemy URL |
| `MIRSAD_SECRET_KEY` | generated, stored with mode 600 | JWT signing. The audit HMAC key is derived from it. |
| `MIRSAD_POLICY_PATH` | `configs/policies/default.yaml` | Initial policy, used when the DB has none |
| `MIRSAD_UPSTREAMS_PATH` | `configs/upstreams.yaml` | Upstream tool servers |
| `MIRSAD_APPROVAL_TIMEOUT_S` | `120` | Approval expiry |
| `MIRSAD_MAX_RESULT_CHARS` | `200000` | Size at which tool results are truncated |
| `MIRSAD_AUDIT_PAYLOAD_MAX_CHARS` | `20000` | Audit payload size cap (enforced by the audit log) |
| `MIRSAD_TOKEN_TTL_HOURS` | `12` | JWT lifetime |
| `MIRSAD_CORS_ORIGINS` | Vite dev server | Allowed browser origins (JSON list) |
| `MIRSAD_ENABLE_DEMO` | `false` | Mount `/api/demo/*` |
| `MIRSAD_LLM_BASE_URL`, `MIRSAD_LLM_MODEL`, `MIRSAD_LLM_API_KEY` | Ollama, `qwen2.5:7b` | Used by the OpenAI proxy and the demo agent |
| `MIRSAD_VAPID_PUBLIC_KEY`, `MIRSAD_VAPID_PRIVATE_KEY` | empty | Enable Web Push |
| `MIRSAD_ADMIN_PASSWORD` (`MIRSAD_ADMIN_USERNAME`) | – | Creates the first admin at startup when there are no users |

## 6. Testing

```bash
"$PY" -m pytest tests/api -q
```

The suite has 185 tests (about 11 s):

| File | What it covers |
|---|---|
| `test_gateway.py` | Gateway unit tests with fakes for every other area: fail-closed paths, monitor mode, concurrency, approvals, latency, truncation, executor errors and timeouts, replay |
| `test_api_auth.py` | Login, throttling, 401 and 403 on every protected route family, token and agent-key handling |
| `test_api_guard.py` | Guard API, approvals through the API from a concurrent task, inspection, invoking an in-process Python upstream |
| `test_api_admin.py` | Audit (verify, tamper detection, replay, export), stats, policy hot reload and rollback, agent and user CRUD |
| `test_api_http.py` | Headers, CSP, body limit, CORS, SPA serving, lifespan, `/mcp` and OpenAI mounting |
| `test_api_stream.py` | SSE against a live uvicorn server |
| `test_api_demo.py` | Demo Console with a scripted LLM |
| `test_cli.py` | The command line |
| `test_integration_real.py` | All real modules, including MCP over streamable HTTP. The planted content is a neutral placeholder that a thin stub around the real detector scores as an injection. |
| `test_e2e_http.py` | End-to-end over real HTTP with the real modules (no fakes): `mirsad init --demo`, the app built by `mirsad serve` with `MIRSAD_ENABLE_DEMO=true` running on an in-process uvicorn server, admin login, stats, agent creation, demo tools checked against `configs/policies/default.yaml` (internal e-mail allowed, `export_customers` with `count: 200` denied by the constraint, `search_customers` over the limit denied, external e-mail paused for approval), an approval sent **from a second process** while the agent's invoke call waits, audit verify, replay of every decision, CSV export and the OpenAPI route inventory |

The API tests use the real storage, auth, audit, approvals, taint and policy modules, and a deterministic fake detector (`tests/api/fakes.py`). The fake detector reacts to neutral placeholder strings (`SAMPLE-FLAGGED-TEXT`, `sample-suspicious-text` and an Arabic placeholder), so no attack text is kept in the test suite. `test_e2e_http.py` uses only real components; `test_integration_real.py` uses real components with the placeholder stub described above.

**Route inventory** (measured on an app with the demo enabled): 52 method+path routes, of which 43 operations on 38 paths are in `/openapi.json` (56 component schemas). The rest are not in the schema on purpose: `/mcp` (GET/POST/DELETE plus the mount), `/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json` itself and the SPA catch-all. Without the demo, the 5 `/api/demo/*` operations are absent.

## 7. Limitations

- **One process owns the in-memory state.** Taint sessions, rate-limit counters and the login throttle are in-memory. Running several workers behind a load balancer would split them. Policy activations do propagate across processes, through the maintenance task.
- **Replay depends on what the audit log kept.** Replay is exact for decisions whose payload was stored whole. Redaction (IBANs, card numbers, secrets) or truncation to `audit_payload_max_chars` can change the replayed inputs; such cases are flagged in `details.notes`. Inspection replay uses the *current* detector model, because the detector is not versioned per event.
- **Waiting for approval holds the HTTP request open.** With `wait=true` the request stays open until a human decides (up to `approval_timeout_s`). A client that disconnects leaves the approval pending until it expires.
- **Agents that share a session id share taint state.** Taint is keyed by the policy agent id and the session id. Two credentials that use the same policy agent and the same `session_id` share taint state.
- **MCP calls are not attributed to a credential.** The `principal` (credential id) is recorded for Guard and invoke calls. The MCP HTTP adapter authenticates on its own and does not yet set `principal_var`, so MCP-originated audit events have `principal: null`.
- **Some statistics are cheaper on SQLite.** The JSON-derived statistics (latency, layers, injections) use SQLite JSON1. On other databases the payloads of the time window are parsed in Python, which is slower for very large windows.
- **The login throttle can be bypassed by changing IP.** It is per process and keyed on the client IP as seen by the server. Behind a reverse proxy, all clients share the proxy's IP unless proxy headers are trusted, which they are not by default.
