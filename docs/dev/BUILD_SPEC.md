# Mirsad — Build Specification (internal engineering contract)

This document is the single source of truth for how Mirsad's components fit together.
Every module MUST implement the public interface written here exactly (names, argument
names, return types). Internals are up to the implementer. If you need a shared type that
is not in `src/mirsad/models.py`, define it inside your own module — **never edit
`models.py`, `config.py` or `pyproject.toml`** (they are owned by the integrator). If you
need an extra dependency, install it into the venv for local testing AND write its name +
reason to `docs/dev/deps-requests/<your-area>.txt`.

## 0. Environment & conventions

* Python: `PY="/private/tmp/claude-501/-Users-mlk-Library-Application-Support-Claude-scratch-workspaces-a3fe123c-8cee-4206-b5ca-2e993f262322-ef3da01d-033e-428f-8b54-e9cdf210ed02-scratch-2026-10-11-181102/b859e439-f2cd-483e-a0a1-02fa31977c8d/scratchpad/py312/bin/python"` (3.12, all deps from pyproject installed, project installed editable). Always quote paths — the project path contains spaces.
* Install extra packages: `"$PY" -m pip install <pkg>` (and record the request, see above).
* Project root (ROOT): `/Users/mlk/Library/Application Support/Claude/scratch-workspaces/a3fe123c-8cee-4206-b5ca-2e993f262322/ef3da01d-033e-428f-8b54-e9cdf210ed02/scratch-2026-10-11-181102/mirsad`
* Run tests: `cd "$ROOT" && "$PY" -m pytest tests/<area> -q`. Lint: `"$PY" -m ruff check src tests demo bench`.
* Node 24 + npm are available for the web app (`web/`).
* Ollama is running at `http://127.0.0.1:11434` with model `qwen2.5:7b` (OpenAI-compatible API at `/v1`). Tests that need it must be marked `@pytest.mark.llm`.
* Style: type hints everywhere, pydantic v2 models, `logging.getLogger("mirsad.<area>")` (no print in library code), short docstrings, comments only where the *why* is non-obvious. Async for I/O paths. Ruff-clean (`pyproject.toml` rules).
* Tests: pytest, `tests/<area>/test_*.py`, use `tmp_path` for files/DBs. `asyncio_mode=auto` is on. Aim for meaningful coverage of every public function, including negative / adversarial cases.
* Fictional organisation for all demo data: **Najd Trading Co.**, internal domain `najd-trading.example`. Attacker domains use the `.example` TLD (`evil.example`, `exfil-hub.example`, `free-prizes.example`, …). Never use real company domains or real people's data.
* Bilingual: every user-facing message that can reach an approver/admin has English and Arabic text (`message` / `message_ar`).

## 1. Architecture overview

```
 Agent runtime (any LLM)                                   Upstream tools
 ───────────────────────     ┌────────────── Mirsad gateway ───────────────┐    ─────────────────
  MCP client  ───────────────►  MCP proxy (stdio / streamable HTTP /mcp)    │
  OpenAI-style tool calling ─►  OpenAI-compatible proxy /v1/chat/completions│──► MCP servers (stdio/http/in-process)
  SDK / any framework ───────►  Guard API /v1/guard/*, /v1/tools/*/invoke   │──► HTTP tools
                             │                                              │
                             │   Gateway pipeline (mirsad.gateway)          │
                             │    check_call:  Policy ─► RateLimit ─► Taint ─► combine ─► Approval?
                             │    inspect_result: Detector ─► Sanitize/Spotlight ─► Taint register
                             │    every step ─► Audit log (HMAC hash chain)  │
                             └────────┬──────────────────────┬──────────────┘
                                      │ SSE / Web Push       │ REST + SSE
                              Approver PWA (/approve)   Admin dashboard (/)
```

Package layout (`src/mirsad/`):

| Path | Owner area | Purpose |
|---|---|---|
| `models.py`, `config.py` | integrator | shared types / settings (read-only for others) |
| `policy/` | policy | YAML policy language: schema, parser, validator, engine, rate limiter, sink resolution |
| `taint/` | taint | trust labelling, value extraction, provenance checks |
| `detector/` | detector | normalisation (AR/EN), rules, ML model, ensemble, sanitiser, training |
| `storage/` | audit | SQLAlchemy engine/session + ORM tables |
| `audit/` | audit | hash-chained audit log, verification, query, export, redaction |
| `approvals/` | audit | approval workflow, notifier (SSE pub/sub + Web Push), approver summaries |
| `auth.py` | audit | password hashing, JWT, agent API keys, FastAPI dependencies |
| `gateway.py` | api | the decision pipeline (`Gateway`) |
| `api/` | api | FastAPI app factory + routers |
| `adapters/` | adapters | upstream manager (MCP/HTTP/in-process), MCP proxy server, OpenAI-compatible proxy |
| `sdk/` | adapters | Python client SDK |
| `cli.py` | api | `mirsad` command line |
| `static/` | web | built dashboard + PWA (output of `web/` build) |

Other top-level dirs: `configs/` (policies, upstreams), `demo/` (simulated workspace, MCP server, demo agent), `bench/` (Mirsad-Bench), `data/detector/` (dataset), `web/` (React+TS source), `tests/`, `docs/`, `scripts/`.

## 2. Policy language (`mirsad.policy`)

### 2.1 YAML schema (version 1)

```yaml
version: 1
organization:
  name: Najd Trading Co.
  internal_domains: [najd-trading.example]
defaults:
  decision: deny            # tools not matched by any agent tool entry
  approval_timeout_s: 120
detector:                   # global defaults; tools/agents may override `detector:` keys
  flag_threshold: 0.5       # score >= flag  -> label suspicious, action "flag"
  block_threshold: 0.8      # score >= block -> on_detect action
  on_detect: sanitize       # sanitize | block | flag
  spotlight: true           # wrap untrusted content with data-markers before returning it
taint:
  enabled: true
  destination_params: [to, cc, bcc, recipient, url, to_iban, webhook]
  trusted_fields: [from, sender, id, email_id, date, received_at, customer_id, doc_id]
  untrusted_to_external_sink: require_approval   # session ingested untrusted content, call hits external sink
  confidential_to_external_sink: require_approval # arguments carry values from confidential results to external sink
  untrusted_controls_destination: deny           # a destination arg value came from untrusted (non-trusted-field) content
  after_injection_high_risk: require_approval    # injection detected earlier in session -> any high/critical risk tool
agents:
  - id: email-crm-assistant
    name: Email & CRM Assistant
    description: Reads mail, looks up customers, drafts replies.
    tools:
      list_emails:      {allow: true, trust: untrusted, sensitivity: internal, scan: true}
      read_email:       {allow: true, trust: untrusted, sensitivity: internal, scan: true}
      send_email:
        allow: true
        sink: dynamic
        sink_params: [to, cc, bcc]
        risk: medium
        constraints:
          to:      {domain_in: [najd-trading.example], on_violation: require_approval}
          body:    {max_length: 20000}
        rate_limit: {max_calls: 20, per_seconds: 3600}
      search_customers:
        allow: true
        sensitivity: confidential
        constraints:
          limit: {max: 50}
      get_customer:     {allow: true, sensitivity: confidential}
      export_customers:
        allow: true
        sensitivity: confidential
        risk: high
        approval: on_risk
        constraints:
          count: {max: 50, on_violation: deny}
        rate_limit: {max_calls: 3, per_seconds: 3600}
      update_customer_note: {allow: true, risk: low}
      delete_customer:  {allow: true, risk: critical, approval: always}
      fetch_url:
        allow: true
        trust: untrusted
        scan: true
        sink: external
        constraints:
          url: {pattern: "^https?://", not_pattern: "(?i)(localhost|127\\.0\\.0\\.1|169\\.254\\.|\\.internal)"}
      list_documents:   {allow: true, sensitivity: internal}
      read_document:    {allow: true, trust: untrusted, sensitivity: internal, scan: true}
      transfer_funds:   {allow: true, risk: critical, approval: always, sink: external,
                         constraints: {amount_sar: {max: 10000, on_violation: deny}}}
      "*":              {allow: false}
rules:                      # optional global rules, evaluated after tool entries
  - id: no-bulk-export-to-email
    description: Never e-mail more than 50 customer records.
    when: {tool: send_email, arg_matches: {body: "(?s)\\A(?:[^@]*@){51}"}}   # linear-time; (.*@.*){51,} backtracks exponentially (ReDoS)
    action: deny
```

Tool keys may be exact names or globs (`crm_*`, `*`); exact beats glob, longer glob beats shorter.
Per-tool keys: `allow` (bool), `trust` (trusted|untrusted, trust of its **results**),
`sensitivity` (public|internal|confidential, of its results), `sink` (none|internal|external|dynamic),
`sink_params` (args holding destinations, for `dynamic`), `risk` (low|medium|high|critical),
`approval` (never|on_risk|always), `scan` (bool, run detector on results; default true when
trust=untrusted), `constraints` (per-argument), `rate_limit`, `detector` (overrides).

Constraint operators (all optional, AND-ed): `max`, `min` (numbers), `max_length`, `min_length`,
`enum` / `in`, `not_in`, `pattern`, `not_pattern` (Python regex, `re.search`), `domain_in`,
`domain_not_in` (applies to e-mail addresses / URLs, also to every element of a list or comma-separated string),
`max_items` (lists), `required` (bool), `type` (string|number|integer|boolean|array|object). Each constraint
may set `on_violation: deny | require_approval` (default `deny`).

`rules[].when` keys: `tool` (name or glob), `agent`, `arg_matches` {arg: regex}, `sink` (none|internal|external),
`session_tainted` (bool), `min_risk`. `rules[].action`: allow | deny | require_approval.

Approval semantics: `always` → REQUIRE_APPROVAL on every call; `on_risk` → REQUIRE_APPROVAL when the
combined risk score of the call ≥ 0.6 (HIGH) *or* tool risk is high/critical and any taint reason fired;
`never` → never escalate (deny reasons still deny).

### 2.2 Public interface

```python
# mirsad/policy/__init__.py re-exports these
class PolicyError(Exception): ...                     # raised for invalid policy documents

class PolicyDocument(BaseModel): ...                  # parsed & validated YAML (pydantic)

def load_policy(text: str) -> PolicyDocument          # raises PolicyError with readable messages
def validate_policy(text: str) -> list[str]           # [] when valid, else human-readable errors (line refs if possible)

class DetectorSettings(BaseModel):
    flag_threshold: float = 0.5; block_threshold: float = 0.8
    on_detect: Literal["sanitize","block","flag"] = "sanitize"; spotlight: bool = True

class TaintSettings(BaseModel):
    enabled: bool = True; destination_params: list[str]; trusted_fields: list[str]
    untrusted_to_external_sink: Action; confidential_to_external_sink: Action
    untrusted_controls_destination: Action; after_injection_high_risk: Action

class PolicyEvaluation(BaseModel):
    reasons: list[Reason]          # policy/ratelimit layer reasons (empty == nothing objected)
    profile: ToolProfile
    sink: SinkKind
    rate_counts: dict[str, int]    # counters used, stored in audit for deterministic replay

class RateLimiter:                 # in-memory sliding window; thread-safe
    def hit(self, key: str, per_seconds: float, now: float) -> int   # records the call, returns count in window incl. this one
    def peek(self, key: str, per_seconds: float, now: float) -> int

class PolicyEngine:
    def __init__(self, document: PolicyDocument, *, rate_limiter: RateLimiter | None = None)
    @classmethod
    def from_yaml(cls, text: str) -> "PolicyEngine"
    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine"
    document: PolicyDocument
    yaml_text: str
    version: str                                         # sha256 hex of normalised YAML text
    def agent_ids(self) -> list[str]
    def tool_profile(self, agent_id: str, tool: str) -> ToolProfile
    def visible_tools(self, agent_id: str, tools: list[str]) -> list[str]   # tools with allow=true
    def resolve_sink(self, call: ToolCall, profile: ToolProfile) -> SinkKind
    def evaluate_call(self, call: ToolCall, *, now: float | None = None,
                      rate_counts: dict[str, int] | None = None,
                      session_tainted: bool = False) -> PolicyEvaluation
        # rate_counts given  -> replay mode: use these counts, do not touch the limiter
    def approval_required(self, profile: ToolProfile, risk_score: float, taint_fired: bool) -> bool
    def detector_settings(self, agent_id: str, tool: str) -> DetectorSettings
    def taint_settings(self, agent_id: str) -> TaintSettings
    def internal_domains(self) -> list[str]
```

Reason codes (policy layer): `UNKNOWN_AGENT`, `TOOL_NOT_ALLOWED`, `CONSTRAINT_VIOLATION`
(evidence: param, operator, expected, actual), `RATE_LIMIT` (layer `ratelimit`), `RULE_MATCH`, `APPROVAL_ALWAYS`.
Unknown agent → DENY. Tool risk contributes `risk_score` (low .1, medium .3, high .6, critical .9) on a
`TOOL_RISK` reason with action ALLOW (informational) so the gateway can compute the combined risk.

`resolve_sink`: `none|internal|external` returned as-is; `dynamic` → EXTERNAL if any value in
`sink_params` args (strings, lists, comma/semicolon separated) has an e-mail/URL domain that is not one of
`internal_domains` (subdomains of internal domains count as internal), INTERNAL if all are internal, NONE if no values.

## 3. Taint tracking (`mirsad.taint`)

```python
class TaintTracker:
    def __init__(self, *, max_values_per_session: int = 2000, session_ttl_s: float = 6 * 3600)
    def snapshot(self, session_id: str, agent_id: str) -> SessionSnapshot      # creates empty if unknown
    def register_result(self, result: ToolResult, profile: ToolProfile,
                        detection: DetectionResult | None, settings: TaintSettings) -> SessionSnapshot
    def evaluate_call(self, call: ToolCall, profile: ToolProfile, sink: SinkKind,
                      settings: TaintSettings, snapshot: SessionSnapshot | None = None) -> list[Reason]
        # snapshot given -> replay mode (pure function of inputs); otherwise uses live session state
    def note_call(self, call: ToolCall) -> None                                 # increments call_count
    def reset(self, session_id: str | None = None) -> None

def extract_values(text_or_structured, *, trusted_fields: list[str]) -> list[tuple[str, str, str | None, bool]]
    # -> (value, kind, field_path, from_trusted_field). kinds: email, url, domain, iban, phone, number(>=6 digits), id, ngram
```

Rules implemented by `evaluate_call` (each yields a `Reason(layer="taint", ...)`):

| Code | Fires when | Default action |
|---|---|---|
| `TAINT_UNTRUSTED_TO_EXTERNAL` | session has ingested untrusted content and `sink == EXTERNAL` | `settings.untrusted_to_external_sink` |
| `TAINT_CONFIDENTIAL_TO_EXTERNAL` | an argument contains a value (email/phone/iban/id/number/ngram≥8 words) recorded from a CONFIDENTIAL result and `sink == EXTERNAL` | `settings.confidential_to_external_sink` |
| `TAINT_UNTRUSTED_DESTINATION` | a destination param value (or its domain) was first seen in an UNTRUSTED result outside `trusted_fields` and never in a trusted result | `settings.untrusted_controls_destination` |
| `TAINT_AFTER_INJECTION` | session had an injection detection (label `injection`) and tool risk ≥ high | `settings.after_injection_high_risk` |

Evidence must name the source tool + call_id + field so the approver can see *where the data came from*.
Matching is case-insensitive, Arabic-normalised for n-grams, and must handle values embedded in longer
strings (e.g. an e-mail inside a body). Risk scores: untrusted→external 0.6, confidential→external 0.7,
untrusted destination 0.9, after injection 0.8.

## 4. Injection detector (`mirsad.detector`)

```python
@dataclass
class NormalizedText: text: str; signals: list[str]; offsets: list[int]   # offsets[i] = index in original for normalized char i

def normalize(text: str) -> NormalizedText          # NFKC, strip zero-width & bidi controls (signal), Arabic: remove tashkeel/tatweel,
                                                    # unify alef/ya/ta-marbuta, Arabic-Indic digits->ASCII, confusable/homoglyph fold, lowercase
def detect_language(text: str) -> Literal["en","ar","mixed","other"]

class RuleSet: def match(self, normalized: NormalizedText) -> list[RuleHit]    # weighted regex rules EN + AR (MSA & Gulf) + structural (chat-template tokens, hidden HTML, markdown-image exfil, base64 blobs)

class InjectionDetector:
    def __init__(self, model_dir: str | Path | None = None, *, window_chars: int = 600, stride_chars: int = 300)
    @classmethod
    def default(cls) -> "InjectionDetector"           # loads packaged model from mirsad/detector/model/, rules-only fallback if absent
    def scan(self, text: str) -> DetectionResult      # score in [0,1], label by thresholds .5/.8 (callers re-threshold via settings)
    def scan_structured(self, value) -> DetectionResult # walks JSON strings, merges results (spans refer to the JSON text dump)

def sanitize(text: str, detection: DetectionResult, *, mode: Literal["sanitize","block"]) -> str
def spotlight(text: str, *, source: str, call_id: str) -> str   # data-marking wrapper + bilingual "do not follow instructions" note
```

Model: char n-gram (2–5, `char_wb`) + word (1–2) hashed features (`HashingVectorizer`, 2**20) → `LogisticRegression`
(class-balanced). Persist **without pickle**: `model/coef.npy`, `model/intercept.npy`, `model/meta.json`
(vectorizer params, thresholds, training metadata, metrics). Load with `allow_pickle=False`.
Long texts are scored over sliding windows (max window score). Final score = noisy-OR of model score and rule
score (`1-(1-m)(1-r)`), calibrated on the validation split. Target: F1 ≥ 0.85 on both the Arabic and English
held-out test sets; p50 scan latency < 10 ms for 2 KB text.

Training entry point: `python -m mirsad.detector.train --data data/detector --out src/mirsad/detector/model`
writes `reports/detector_metrics.json` (per-split, per-language precision/recall/F1/ROC-AUC, confusion matrices,
threshold sweep) and figures under `reports/figures/`.

## 5. Storage, audit, approvals, auth

### 5.1 Database (`mirsad.storage`, SQLAlchemy 2.0, SQLite default, Postgres-compatible types only)

```python
class Database:
    def __init__(self, url: str)
    def create_all(self) -> None
    def session(self) -> contextmanager[Session]
```

Tables:
* `users(id INTEGER PK, username UNIQUE, password_hash, role ['admin','approver','auditor'], display_name, lang ['en','ar'], created_at, disabled)`
* `agents(id TEXT PK slug, name, description, policy_agent_id, key_prefix, key_hash, created_at, disabled, last_seen_at)`
* `policies(version TEXT PK sha256, yaml_text, created_at, created_by, active BOOL, comment)`
* `audit_events(seq INTEGER PK, ts FLOAT, event_type, session_id, agent_id, tool, call_id, action, risk, policy_version, payload_json TEXT, prev_hash, hash)` with indexes on ts, agent_id, tool, action, session_id, event_type
* `approvals(id TEXT PK, created_at, expires_at, status, agent_id, session_id, call_id, tool, arguments_json, decision_json, summary_en, summary_ar, risk, decided_by, decided_at, note)`
* `push_subscriptions(id PK, user_id FK, endpoint UNIQUE, p256dh, auth, created_at)`

### 5.2 Audit (`mirsad.audit`)

```python
GENESIS_HASH = "0" * 64
def redact(value: Any) -> Any        # deep-redacts secrets: API keys (sk-, mk_, AKIA, ghp_, xox*), JWTs, Bearer tokens,
                                     # PEM keys, password/secret/token fields, card numbers (Luhn) -> last4, Saudi national IDs/IBAN -> masked
class AuditLog:
    def __init__(self, db: Database, hmac_key: bytes, *, payload_max_chars: int = 20_000)
    def append(self, event_type: str, *, session_id=None, agent_id=None, tool=None, call_id=None,
               action=None, risk=None, policy_version=None, payload: dict | None = None) -> AuditEvent   # redacts, chains, thread-safe
    def verify(self) -> AuditVerifyReport          # ok, checked, head_seq, head_hash, first_bad_seq, message
    def get(self, seq: int) -> AuditEvent | None
    def query(self, *, agent_id=None, tool=None, action=None, event_type=None, session_id=None, call_id=None,
              since=None, until=None, text=None, limit=100, offset=0, order="desc") -> tuple[list[AuditEvent], int]
    def export(self, fmt: Literal["json","csv"], **filters) -> str
    def head(self) -> tuple[int, str]
```
Hash: `HMAC-SHA256(key, prev_hash + "|" + canonical_json(event_without_hash))` where canonical JSON = sorted keys,
no whitespace, ensure_ascii=False. Event types used by the gateway: `tool_call.decision`, `tool_result.inspection`,
`approval.requested`, `approval.decided`, `policy.activated`, `agent.created`, `agent.key_rotated`, `user.created`,
`auth.login_failed`, `system.started`, `audit.verified`.

### 5.3 Approvals (`mirsad.approvals`)

```python
class Notifier:                                  # in-process pub/sub for SSE + optional Web Push
    async def publish(self, event: str, data: dict) -> None
    def subscribe(self) -> AsyncIterator[tuple[str, dict]]   # async generator, one queue per subscriber
    async def web_push(self, subscriptions: list, payload: dict) -> int   # no-op when VAPID keys absent

def summarize(call: ToolCall, decision: Decision, *, agent_name: str, lang: Literal["en","ar"]) -> str
    # plain-language 1–3 sentences: what the agent wants, why Mirsad paused it, where the data came from

class ApprovalService:
    def __init__(self, db: Database, notifier: Notifier, *, timeout_s: float = 120.0,
                 auto_decider: Callable[[ApprovalRecord], bool | None] | None = None)   # auto_decider used by bench/tests
    async def request(self, call: ToolCall, decision: Decision, *, agent_name: str) -> ApprovalRecord
    async def wait(self, approval_id: str, timeout_s: float | None = None) -> ApprovalRecord  # expires -> EXPIRED
    async def decide(self, approval_id: str, *, approve: bool, user: str, note: str | None = None) -> ApprovalRecord
    def get(self, approval_id: str) -> ApprovalRecord | None
    def list(self, *, status: ApprovalStatus | None = None, limit: int = 100) -> list[ApprovalRecord]
    def expire_overdue(self) -> int
```
Deciding an already-decided approval raises `ValueError`. Decisions publish `approval.decided` on the notifier;
requests publish `approval.requested` (payload = record JSON).

### 5.4 Auth (`mirsad/auth.py`)

```python
def hash_password(pw: str) -> str; def verify_password(pw: str, hashed: str) -> bool     # hashlib.scrypt, constant-time compare
def create_token(username: str, role: str, secret: str, ttl_hours: int) -> str             # JWT HS256
def decode_token(token: str, secret: str) -> dict                                           # raises AuthError
def generate_agent_key() -> tuple[str, str, str]          # (full_key "mk_<prefix>_<secret>", prefix, sha256 hash)
def hash_agent_key(key: str) -> str
class AuthError(Exception)
# FastAPI dependencies (implemented in api/deps.py by the api area, using the functions above):
#   require_user(roles=...) -> UserInfo ; require_agent() -> AgentInfo (header: Authorization: Bearer mk_... or X-Mirsad-Key)
```
Login is rate-limited (5 failures / 5 min / username+IP → 429) and failures are audited.

## 6. Gateway pipeline (`mirsad/gateway.py`)

```python
Executor = Callable[[ToolCall], Awaitable[ToolResult]]

class Gateway:
    def __init__(self, *, policy: PolicyEngine, taint: TaintTracker, detector: InjectionDetector,
                 audit: AuditLog, approvals: ApprovalService, agent_names: dict[str, str] | None = None,
                 policy_store: Callable[[str], str | None] | None = None)     # version -> yaml (for replay)
    policy: PolicyEngine                                                     # hot-swappable: set_policy()
    def set_policy(self, engine: PolicyEngine) -> None
    async def check_call(self, call: ToolCall, *, wait_for_approval: bool = True) -> Decision
    async def inspect_result(self, result: ToolResult) -> InspectionOutcome
    async def execute(self, call: ToolCall, executor: Executor) -> GatewayResponse   # check -> run (if allowed) -> inspect
    def replay(self, seq: int) -> ReplayReport       # re-evaluates a stored decision/inspection event; fields: seq, event_type,
                                                     # original_action, replayed_action, match: bool, details
```

`check_call` algorithm: (1) `policy.evaluate_call(call, session_tainted=snapshot.tainted)`; (2) taint reasons via
`taint.evaluate_call` with the resolved sink; (3) `combine_reasons`; (4) if the result is ALLOW but
`policy.approval_required(profile, risk_score, taint_fired)` → REQUIRE_APPROVAL with reason `APPROVAL_POLICY`;
(5) audit `tool_call.decision` with payload `{call, profile, sink, reasons, snapshot, rate_counts, risk_score}`;
(6) if REQUIRE_APPROVAL and `wait_for_approval`: `approvals.request` → `approvals.wait` → final ALLOW (reason
`APPROVED_BY_HUMAN`) or DENY (`DENIED_BY_HUMAN` / `APPROVAL_EXPIRED`), audit `approval.decided`; (7) `taint.note_call`.
`latency_ms` excludes the time spent waiting for a human.

`inspect_result`: profile → if `profile.scan` or trust untrusted → `detector.scan(_structured)`; map score with the
tool's `DetectorSettings` to pass / flag / sanitize / block; `taint.register_result(...)`; spotlight untrusted content
when enabled; truncate to `max_result_chars`; audit `tool_result.inspection` with payload `{result(content truncated),
detection, action, profile}`.

## 7. Adapters

### 7.1 Upstreams (`mirsad.adapters.upstreams`)
`configs/upstreams.yaml`:
```yaml
upstreams:
  - name: workspace
    transport: inprocess          # python import path of an mcp MCPServer instance
    target: demo.workspace_server:server
  # - {name: files, transport: stdio, command: [python, -m, demo.workspace_server]}
  # - {name: remote, transport: http, url: http://127.0.0.1:9000/mcp}
```
```python
class UpstreamManager:
    @classmethod
    def from_file(cls, path) -> "UpstreamManager"
    async def start(self) -> None; async def stop(self) -> None
    async def list_tools(self) -> list[UpstreamTool]           # name, description, input_schema, upstream
    async def call(self, call: ToolCall) -> ToolResult          # executor compatible with Gateway.execute
    def register_python(self, name: str, fn: Callable, description: str, input_schema: dict) -> None  # plain function tools
```
The installed MCP SDK is **v2.x** (`from mcp import Client, StdioServerParameters`; servers:
`from mcp.server.mcpserver import MCPServer`, the renamed FastMCP). Read the installed source under
`.../py312/lib/python3.12/site-packages/mcp/` before using it — v1 examples will not work.

### 7.2 MCP proxy (`mirsad.adapters.mcp_proxy`)
`build_mcp_server(gateway, upstreams, agent_id) -> MCPServer|Server` exposing upstream tools visible to the agent
(policy `visible_tools`), every `call_tool` routed through `gateway.execute`. Denied calls return an MCP tool
error result whose text explains the block (EN + AR). Transports: stdio (`mirsad mcp-proxy`) and streamable
HTTP mounted at `/mcp` on the FastAPI app (agent key required).

### 7.3 OpenAI-compatible proxy (`mirsad.adapters.openai_proxy`)
`POST /v1/chat/completions` (agent key). Before forwarding: every `role: tool` message is inspected with
`gateway.inspect_result` (tool name resolved from the preceding assistant `tool_calls`) and replaced by the inspected
content. After the upstream response: every `tool_calls[i]` is checked with `gateway.check_call`; denied calls are
removed and an explanatory assistant text is appended; if all are removed `finish_reason` becomes `"stop"`.
Session id: header `X-Mirsad-Session` else hash of the first user message. Non-streaming only (stream=true → 400).

### 7.4 SDK (`mirsad.sdk`)
```python
class MirsadClient:
    def __init__(self, base_url: str, api_key: str, *, session_id: str | None = None, timeout: float = 150)
    def check_call(self, tool: str, arguments: dict, *, call_id: str | None = None) -> Decision
    def inspect_result(self, tool: str, call_id: str, content: str | Any) -> InspectionOutcome
    def invoke(self, tool: str, arguments: dict) -> GatewayResponse
    def tools(self) -> list[dict]                              # OpenAI function-calling schemas of visible tools
    def guard(self, fn=None, *, name: str | None = None)      # decorator: check -> run -> inspect; raises MirsadBlocked
class MirsadBlocked(Exception): decision: Decision
class AsyncMirsadClient: same API, async
```

## 8. REST API (FastAPI, `mirsad.api.create_app(settings) -> FastAPI`)

JSON everywhere; errors `{"detail": str}`. Human auth: `Authorization: Bearer <JWT>`; agent auth: `Bearer mk_...` or `X-Mirsad-Key`.

| Method & path | Role | Body → Response |
|---|---|---|
| GET `/healthz` | – | `{status:"ok", version}` |
| POST `/api/auth/login` | – | `{username,password}` → `{access_token, token_type:"bearer", user:{username,role,display_name,lang}}` |
| GET `/api/auth/me` | any user | user |
| POST `/v1/guard/tool-call` | agent | `{session_id, tool, arguments, call_id?, wait?:bool=true}` → `Decision` |
| POST `/v1/guard/tool-result` | agent | `{session_id, call_id, tool, content, structured?}` → `InspectionOutcome` |
| POST `/v1/tools/{tool}/invoke` | agent | `{session_id, arguments}` → `GatewayResponse` |
| GET `/v1/tools` | agent | `[{name, description, input_schema, profile}]` (visible only) |
| POST `/v1/chat/completions` | agent | OpenAI chat completions request/response |
| `/mcp` | agent | MCP streamable HTTP |
| POST `/api/detector/scan` | any user | `{text}` → `DetectionResult` |
| GET `/api/approvals?status=&limit=` | approver/admin | `[ApprovalRecord]` |
| GET `/api/approvals/{id}` | approver/admin | `ApprovalRecord` |
| POST `/api/approvals/{id}/decision` | approver/admin | `{approve: bool, note?}` → `ApprovalRecord` |
| GET `/api/stream` | any user | SSE: events `approval.requested`, `approval.decided`, `audit.event` (data = JSON) |
| POST `/api/push/subscribe` | any user | Web Push subscription JSON → 204 ; GET `/api/push/vapid` → `{public_key}` |
| GET `/api/audit/events?agent_id&tool&action&event_type&session_id&since&until&q&limit&offset` | admin/auditor | `{items:[AuditEvent], total}` |
| GET `/api/audit/events/{seq}` | admin/auditor | `AuditEvent` |
| POST `/api/audit/verify` | admin/auditor | `AuditVerifyReport` |
| POST `/api/audit/events/{seq}/replay` | admin/auditor | `ReplayReport` |
| GET `/api/audit/export?format=json|csv&...filters` | admin/auditor | file download |
| GET `/api/stats/overview?hours=24` | any user | `{total_calls, allowed, denied, approvals_required, approvals_pending, injections_detected, results_sanitized, median_latency_ms, p95_latency_ms, audit_ok, by_tool:[{tool, allowed, denied, approval}], by_layer:[{layer,count}]}` |
| GET `/api/stats/timeseries?hours=24&bucket_minutes=60` | any user | `[{t, allowed, denied, require_approval, injections}]` |
| GET `/api/policies` | admin/auditor | `{active:{version, yaml_text, created_at, created_by}, versions:[{version, created_at, created_by, active, comment}]}` |
| GET `/api/policies/{version}` | admin/auditor | policy |
| POST `/api/policies/validate` | admin | `{yaml_text}` → `{valid, errors:[str]}` |
| PUT `/api/policies` | admin | `{yaml_text, comment?}` → activated version (hot-reloads gateway) |
| GET/POST `/api/agents`, POST `/api/agents/{id}/rotate-key`, PATCH/DELETE `/api/agents/{id}` | admin | agent CRUD; key shown only once on create/rotate: `{agent, api_key}` |
| GET/POST `/api/users`, PATCH/DELETE `/api/users/{username}` | admin | user CRUD (no password hashes returned) |
| GET `/api/tools` | admin/auditor | discovered upstream tools + profile per agent |
| POST `/api/demo/chat` | any user (demo only) | `{message, session_id?, protected: bool, lang?}` → `{reply, session_id, steps:[{tool, arguments, decision?, result_preview, inspection?}], attacker_inbox:[...]}` |
| POST `/api/demo/reset`, GET `/api/demo/state`, GET `/api/demo/scenarios` | any user (demo only) | demo world control |

Static: `/` → dashboard SPA (`static/index.html`), `/approve` → approver PWA (`static/approve.html`), assets under `/assets`.
Security headers on every response: CSP (self), X-Content-Type-Options, X-Frame-Options DENY, Referrer-Policy.
Request size limit 1 MB (413).

## 9. CLI (`mirsad`, click)
`serve`, `init [--demo] [--admin-password]`, `policy validate FILE`, `policy activate FILE`, `audit verify`,
`audit export --format`, `audit replay SEQ`, `scan TEXT|--file`, `agent create NAME --policy-agent ID`,
`user create USERNAME --role`, `mcp-proxy --agent-key KEY [--url]` (stdio MCP server forwarding to a running gateway
over HTTP), `detector train`.

## 10. Demo workspace (`demo/`)

`demo/world.py` — `World` dataclass: in-memory simulated Najd Trading Co. workspace, deterministic seed, bilingual.
```python
class World:
    def __init__(self, seed: int = 7)
    emails: list[dict]        # id, folder, from, to, subject, body, date, lang
    customers: list[dict]     # id, name, name_ar, email, phone, city, tier, balance_sar, notes  (~120, Arabic & English names, fake data)
    web_pages: dict[str, dict]# url -> {title, body, lang}
    documents: dict[str, dict]# id -> {title, body, owner, lang, source: internal|external}
    outbox: list[dict]; http_log: list[dict]; deleted: list[str]; exports: list[dict]; transfers: list[dict]; notes_log: list[dict]
    side_effects: list[dict]  # unified {tool, args, ts}
    def reset(self) -> None
    def plant(self, vector: Literal["email","web","document","crm_note"], target_id: str, payload: str, *, position: Literal["start","middle","end"]="end") -> None
    def snapshot(self) -> dict
TOOLS: dict[str, ToolSpec]     # ToolSpec(name, description, input_schema (JSON schema), fn(world, **args) -> dict|list|str)
def call_tool(world: World, name: str, arguments: dict) -> Any   # validates args, returns JSON-serialisable value
```
Tools (exact names / args): `list_emails(folder="inbox", limit=10)`, `read_email(email_id)`, `send_email(to, subject, body, cc=None)`,
`search_customers(query, limit=10)`, `get_customer(customer_id)`, `export_customers(query="", count=10)` (returns CSV text),
`update_customer_note(customer_id, note)`, `delete_customer(customer_id)`, `fetch_url(url)`, `list_documents()`,
`read_document(doc_id)`, `transfer_funds(to_iban, amount_sar, memo="")`.

`demo/workspace_server.py` exposes `server` (an `MCPServer`) wrapping a module-level `WORLD = World()` with all tools;
runnable as stdio (`python -m demo.workspace_server`). `demo/agent.py` — `DemoAgent(llm_base_url, model, backend)`, a tool-calling loop
over the OpenAI-compatible API (Ollama), max 8 steps, system prompt in EN/AR; backends: `DirectBackend(world)` (unprotected)
and `GatewayBackend(gateway, agent_id, session_id, executor)` (protected, in-process) and `HttpBackend(base_url, api_key)`.
Returns a transcript of steps.

## 11. Mirsad-Bench (`bench/`)

Scenario files `bench/scenarios/*.yaml` (EN, AR, mixed). Entities:
* **user_tasks** — `{id, lang, prompt, plan:[{tool, args}], success:{...}, reads:[{vector, target}]}` (benign intent; `plan` drives the scripted agent; `reads` lists content the task reads where an injection can be planted).
* **injection_tasks** — `{id, category: exfiltration|destruction|fraud|phishing|privilege, goal, actions:[{tool,args}], success:{...}}`.
* **attack_templates** — `{id, lang: en|ar|mixed, style: ignore_previous|important_instructions|system_impersonation|tool_knowledge|completion|social_engineering|obfuscated|dialect, template}` with `{goal}` / `{actions_text}` placeholders (AgentDojo/InjecAgent-inspired; Arabic MSA + Gulf dialect + code-switched variants).
* Success predicates are evaluated on `World` side effects (e.g. `{sent_to_domain: evil.example}`, `{deleted: C017}`, `{transfer_to: SA..}`, `{fetched_domain: exfil-hub.example}`).

Harness (`python -m bench.run --agent scripted|llm --defense none|full|policy_only|taint_only|detector_only --approver deny|oracle --limit N --out reports/bench/...`):
* **ScriptedAgent** (worst-case compliant): executes the user plan; whenever a tool result still contains the planted payload text (not removed/sanitised), it immediately performs the injection task's actions (fully obedient attacker model), then finishes the plan. Deterministic.
* **LLMAgent**: `demo.agent.DemoAgent` with qwen2.5:7b via Ollama; temperature 0; same tools.
* Metrics per configuration: attack success rate (ASR), utility without attack, utility under attack, benign false-positive rate (benign actions denied), approval-friction rate (benign actions escalated), detector catches, latency p50/p95 per call (excluding human wait). Outputs JSON + CSV + markdown summary + matplotlib figures under `reports/bench/`.
* Benign-only episodes (no injection) measure FPR. Required: ASR reduction ≥ 80 % vs `--defense none`; benign FPR ≤ 5 %.

## 12. Detector dataset (`data/detector/`)

JSONL, one object per line:
```json
{"id":"en-inj-0001","text":"...","label":1,"lang":"en","variety":"en","carrier":"email","attack_type":"data_exfiltration","difficulty":"medium","source":"authored/batch-en-inj","notes":""}
```
* `label` 1 = contains an instruction aimed at an AI agent/model that tries to change its behaviour or trigger actions not requested by its user (prompt injection); 0 = benign (including hard negatives: ordinary imperatives, security articles *discussing* attacks in a descriptive way, quoted examples clearly framed as examples, customer requests).
* `lang`: en | ar | mixed. `variety`: en | msa | gulf | egyptian | levantine | arabizi | mixed.
* `carrier`: email | web | document | crm_note | chat | tool_output | review | ticket | code_comment | plain.
* `attack_type`: none | goal_hijack | data_exfiltration | tool_misuse | role_impersonation | context_ignoring | obfuscated | payload_splitting | social_engineering | markdown_exfil | system_prompt_leak.
* `difficulty`: easy | medium | hard.
* Files: `raw/<batch>.jsonl` (authored), `external/` (public datasets with LICENSE notes), `splits/{train,val,test_en,test_ar,test_mixed}.jsonl` produced by `python -m mirsad.detector.build_dataset` (group split by batch so test batches are never seen in training; augmentation — embedding payloads in carriers, zero-width/homoglyph/tashkeel obfuscation — applied to train only).
* `DATASHEET.md` documents provenance, licences, labelling guidelines, known limitations.

## 13. Web app (`web/`, React 18 + TypeScript + Vite)

Multi-page Vite build → `src/mirsad/static/` (`index.html` dashboard, `approve.html` PWA). Talks only to the REST API above.
Dashboard pages: Login, Overview (KPIs + time-series + by-tool + layer breakdown + audit status), Activity / Audit log
(filters, detail drawer with reasons, detector spans highlighted, taint provenance, Replay + Verify + Export), Approvals
(live queue + history), Policies (YAML editor, validate, diff, activate, versions), Agents (create/rotate/disable; key shown once),
Users, Tools, Detector Playground (EN/AR samples, highlighted spans, score gauge), Demo Console (chat with demo agent, protection
toggle, step timeline with decisions, "attacker inbox" panel). EN/AR language toggle with full RTL support. Accessible:
semantic HTML, labels, keyboard navigation, WCAG AA contrast, `prefers-reduced-motion`, dark/light.
Approver PWA: login, pending cards (risk colour, countdown), detail with plain-language summary, "why paused", "data came from",
args (collapsible), big Approve/Deny with confirm, history, live updates via fetch-based SSE + Notification API + Web Push,
manifest + service worker (offline shell), installable, EN/AR + RTL. Target: decision in < 30 s.

## 14. Integration seams (who provides what)

* `mirsad/textutil.py` (integrator, read-only): `strip_invisible`, `normalize_arabic`, `fold`, `arabic_ratio`,
  `extract_domain`, `domain_matches`, `split_addresses`, regexes `EMAIL_RE`, `URL_RE`, `IBAN_RE`, `PHONE_RE`.
  Use these instead of re-implementing Arabic folding / domain logic (you may add stricter local helpers).
* **Monitor mode**: policy top-level key `mode: enforce | monitor` (default enforce) → `PolicyEngine.mode`.
  In monitor mode the gateway computes and audits the would-be decision (`payload.enforced=false`) but returns ALLOW
  and never sanitises/blocks results (shadow deployment for tuning). `Decision.reasons` still lists what would have fired.
* `mirsad/auth.py` (audit area) also defines:
  ```python
  class UserInfo(BaseModel): username: str; role: Literal["admin","approver","auditor"]; display_name: str = ""; lang: str = "en"
  class AgentInfo(BaseModel): id: str; name: str; policy_agent_id: str
  def authenticate_agent_key(db: Database, key: str) -> AgentInfo | None    # constant-time hash compare, updates last_seen_at, None if disabled/unknown
  def authenticate_user(db: Database, username: str, password: str) -> UserInfo | None
  def create_user(db, username, password, role, display_name="", lang="en") -> UserInfo
  def create_agent(db, agent_id, name, policy_agent_id, description="") -> tuple[AgentInfo, str]   # returns full key once
  def rotate_agent_key(db, agent_id) -> str
  ```
* App wiring (api area): `create_app(settings: Settings | None = None, *, gateway_overrides: dict | None = None) -> FastAPI`.
  On startup it builds `Database`, `AuditLog`, `Notifier`, `ApprovalService`, `PolicyEngine` (active DB version, else
  `settings.policy_path`, persisted as first version), `TaintTracker`, `InjectionDetector.default()`, `UpstreamManager`
  (from `settings.upstreams_path`; missing file → empty), `Gateway`; stores them on `app.state.<name>`
  (`settings, db, audit, notifier, approvals, policy_store, taint, detector, upstreams, gateway`).
  `api/deps.py`: `get_gateway(request)`, `require_agent` → `AgentInfo`, `require_user(*roles)` → `UserInfo`.
* Adapters area provides, and the api area includes in `create_app`:
  ```python
  # mirsad/adapters/openai_proxy.py
  def build_openai_router() -> APIRouter          # uses request.app.state.{gateway,settings} + api.deps.require_agent
  # mirsad/adapters/mcp_proxy.py
  def build_mcp_server(gateway, upstreams, agent_id: str) -> "MCPServer | Server"
  def mcp_http_app(app_state) -> ASGIApp           # streamable-HTTP MCP endpoint; authenticates Bearer agent key per request; mounted at /mcp
  async def run_stdio_proxy(base_url: str, agent_key: str) -> None   # stdio MCP server forwarding to a remote gateway over HTTP
  ```
  If the api area finishes first it must import these lazily and skip mounting when the import fails (log a warning).
* Demo endpoints (`/api/demo/*`, api area) import `demo.world`, `demo.agent` lazily and are only mounted when
  `settings.enable_demo` is true. The in-process upstream `demo.workspace_server:server` shares `demo.workspace_server.WORLD`
  with the demo endpoints so the dashboard can show/reset the same world.
* `demo` and `bench` are importable top-level packages (installed editable); pytest has `pythonpath = [".", "src"]`.
* Gateway agent identity: the policy agent id used for evaluation is `AgentInfo.policy_agent_id`.
