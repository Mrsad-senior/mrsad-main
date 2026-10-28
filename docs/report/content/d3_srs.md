# 1 Introduction

## 1.1 Purpose

This Software Requirements Specification (SRS) defines the requirements for **Mirsad** (مرصاد) version 1.0, a runtime security gateway that protects tool-using large language model (LLM) agents against indirect prompt injection. It is deliverable D3 of the IS499 Senior Project at Prince Sultan University and follows the information items and structure of ISO/IEC/IEEE 29148:2018 for a software requirements specification [@iso29148_2018].

The SRS is written for four groups of readers: the project team, who build and test against it; the supervisor and examiners, who assess whether the system meets its stated objectives; testers, who derive test cases from the acceptance criteria; and future maintainers or adopting organisations, who need to know what the system promises and what it assumes about its environment. The requirement baseline is agreed at milestone M1 (20 October 2026); later changes are recorded as backlog items and reflected in a new revision of this document.

## 1.2 Scope

Mirsad is a self-hosted service placed between an AI agent and the tools the agent calls. It intercepts every tool call and every tool result, whether the agent uses the Model Context Protocol (MCP) or OpenAI-style function calling, and decides for each call whether to allow it, deny it or hold it for a human decision. The decision combines five mechanisms:

- a declarative YAML policy with per-tool and per-parameter constraints, rate limits and global rules;
- taint tracking, which records where values came from and stops untrusted or confidential data from reaching external destinations;
- an Arabic and English prompt-injection detector that scans tool results and removes or marks suspected instructions before the model sees them;
- human approval of high-risk actions through an installable mobile web application;
- a tamper-evident audit log in which every decision can be verified and replayed.

The product also includes an administration dashboard, a simulated enterprise workspace with a demonstration agent, and a benchmark (Mirsad-Bench) for measuring the effect of the gateway.

Mirsad does not protect the LLM against direct jailbreaks typed by its own user, does not provide network- or host-level security, does not secure model weights or training data, and does not offer high availability, horizontal scaling or multi-tenant isolation. It does not process real customer data; all demonstration and benchmark data is synthetic.

The measurable success criteria agreed in the proposal are: a detector F1 score of at least 0.85 on held-out Arabic and English test sets; a reduction in attack success rate of at least 80% relative to an unprotected agent; a benign false-positive rate of at most 5%; and a median added latency of at most 200 ms per tool call.

## 1.3 Definitions, acronyms and abbreviations

Acronyms follow the List of Acronyms of the final project report. Those used most often here are LLM, MCP, PWA (Progressive Web App), SSE (Server-Sent Events), JWT (JSON Web Token), HMAC, VAPID, RBAC, ASR (attack success rate) and FPR (false-positive rate). @tab:d3-glossary defines the project-specific terms.

Table: Glossary of project terms {#tab:d3-glossary widths=1.4,4.6}
| Term | Definition |
|---|---|
| Agent | Software that uses an LLM to plan and carry out a user's request by calling tools. |
| Tool, tool call, tool result | An operation the agent can invoke (for example `send_email`), one invocation with its JSON arguments, and the content the tool returns. |
| Upstream | A tool server (MCP over stdio or HTTP, or in-process Python functions) to which Mirsad forwards allowed calls. |
| Indirect prompt injection | Instructions placed by a third party in content the agent reads, such as an e-mail or web page, that the agent may follow as if they came from its user [@greshake2023indirect]. |
| Policy | The YAML document that lists, per agent, which tools are allowed, their profiles, argument constraints, rate limits and global rules. |
| Tool profile | The policy attributes of a tool: trust and sensitivity of its results, sink kind, risk level, approval mode and detector settings. |
| Trust level | Whether a tool's results are *trusted* or *untrusted* (may contain third-party content). |
| Sensitivity | Classification of a tool's results: *public*, *internal* or *confidential*. |
| Sink | Where a call can send data: *none*, *internal*, *external* or *dynamic* (resolved from destination arguments against the organisation's internal domains). |
| Taint tracking | Recording identifying values (addresses, URLs, IBANs, identifiers, text fragments) from tool results with their source, and checking later calls against that record. |
| Decision | The gateway's verdict on a call: ALLOW, DENY or REQUIRE_APPROVAL, with machine-readable reason codes and English and Arabic explanations. |
| Sanitisation | Removing the spans of a tool result that the detector identified as instructions. |
| Spotlighting | Wrapping untrusted content in data markers with a note telling the model not to follow instructions inside it [@hines2024spotlighting]. |
| Monitor mode | A policy mode in which the would-be decision is computed and audited but every call is allowed, used to trial a policy. |
| Approval request | A suspended call waiting for a human decision; if no decision arrives before the timeout, it expires and the call is denied. |
| Audit event and hash chain | A record of one gateway event; each record's HMAC covers the previous record's hash, so modification, deletion or reordering is detectable. |
| Replay | Re-evaluating a stored decision with its stored policy version and inputs to check that the same action results. |
| Misuse case | A use case performed by an attacker, linked to the use case it threatens and the security use case that mitigates it. |

## 1.4 References

The following documents are referenced by this SRS. External sources are listed in full in the References section.

- ISO/IEC/IEEE 29148:2018, requirements engineering [@iso29148_2018].
- Model Context Protocol specification, revision 2026-07-28 [@mcp2026spec].
- OWASP Top 10 for LLM Applications [@owasp2024llmtop10].
- NCA Essential Cybersecurity Controls [@nca2024ecc] and the Saudi Personal Data Protection Law [@ksa2021pdpl].
- HMAC (RFC 2104) [@rfc2104], JSON Web Token (RFC 7519) [@rfc7519] and scrypt (RFC 7914) [@rfc7914].
- W3C Service Workers [@w3c_serviceworkers], Web Application Manifest [@w3c_appmanifest] and WCAG 2.2 [@w3c2023wcag22].
- Project documents: the SPAP; D2 Work Plan and Budget; D4 Software Design Document; D5 Test Case Specification and Test Results; D6 Software User Guide; the engineering contract `docs/dev/BUILD_SPEC.md`; and the component guides under `docs/` (policy language, taint tracking, detector, audit and approvals, API, integration, benchmark, web UI).

## 1.5 Overview

Section 2 describes the product in its environment: its context, main functions, users, operating environment, constraints, assumptions and dependencies. Section 3 states the specific requirements: functional and non-functional requirements with acceptance criteria, business rules, use cases, external interface requirements and data requirements. Section 4 explains how each class of requirement is verified and where the traceability matrix is kept.

# 2 Overall Description

## 2.1 Product perspective

Mirsad is a new, self-contained component. It does not replace the agent, the LLM or the tools; it is inserted at the tool-calling boundary between them. @fig:d3-context shows the system boundary and the external entities. The business user gives the agent a task; the agent's tool calls pass through Mirsad, which forwards only allowed calls to the enterprise tools and returns inspected, sanitised results. An attacker who can place content in e-mails, web pages or documents that the agent reads is outside the boundary and never interacts with Mirsad directly. Approvers receive approval requests on their phones, and administrators and auditors manage policies, agents and the audit log.

![System context of Mirsad: the gateway between the AI agent and the enterprise tools, with the business user, approver, administrator/auditor and the attacker who plants instructions in content the agent reads](docs/figures/context.png){#fig:d3-context width=6.0}

Mirsad is deployed as one service with a relational database. Agents connect to it as an MCP server, as an OpenAI-compatible chat-completions endpoint, or through a Guard API and Python SDK. Mirsad in turn connects to upstream tool servers as an MCP client. Humans use a web dashboard and an installable approver app, both served by the same service. Because the integration points are standard protocols, an organisation can place Mirsad in front of an existing agent by changing a URL or a configuration entry rather than rewriting the agent.

## 2.2 Product functions

The main functions, detailed as FR1–FR8 in Section 3, are:

1. **Interception (FR1).** Proxy MCP and OpenAI-style tool calls and results, and expose only the tools each agent's policy allows.
2. **Policy enforcement (FR2).** Evaluate per-tool permissions, per-parameter constraints, rate limits and global rules; combine reasons with deny-overrides; allow policies to be validated, activated and rolled back at run time.
3. **Taint tracking (FR3).** Label results by trust and sensitivity, record identifying values with their source, and escalate or block flows of untrusted or confidential data to external sinks.
4. **Injection detection (FR4).** Normalise text, scan untrusted results, and the results of tools marked for scanning such as CRM records, for instructions in English, Modern Standard Arabic, Gulf dialect, Arabizi and mixed text, and sanitise, block or flag them; spotlight untrusted content.
5. **Human approval (FR5).** Suspend high-risk calls, notify approvers in real time with a plain-language bilingual summary, and record their decisions; expire undecided requests as denials.
6. **Audit (FR6).** Append every event to an HMAC hash chain with secrets and identifiers masked; search, export, verify and replay.
7. **Administration (FR7).** Manage agents and keys, users and roles, policies and tools; show live statistics and a detector playground.
8. **Demonstration and evaluation (FR8).** Provide a simulated enterprise workspace, a demonstration agent and the Mirsad-Bench benchmark.

## 2.3 User classes and characteristics

@tab:d3-users describes the classes of users and external actors. The three human roles are enforced by role-based access control (RBAC); agents authenticate with their own API keys. The personas in Section 1.5.1 of the final report (a security analyst, an AI platform engineer and a compliance officer) illustrate the three main human classes.

Table: User classes and actors {#tab:d3-users widths=1.2,0.9,2.6,1.3}
| User class | Role | Characteristics | Main interface |
|---|---|---|---|
| Approver | `approver` | Security analyst or line manager; moderate technical knowledge; often away from a desk; reads Arabic, English or both; must decide within the approval timeout. | Approver PWA on a phone |
| Administrator | `admin` | Security or platform engineer; writes YAML policies, registers agents, manages users; high technical knowledge; uses the system daily during set-up and occasionally afterwards. | Dashboard, CLI |
| Auditor | `auditor` | Compliance or internal-audit officer; searches, verifies, replays and exports the audit log; may read policies but cannot change them or decide approvals. | Dashboard, CLI |
| Agent developer | agent key | Developer who connects an agent through MCP, the OpenAI-compatible endpoint or the SDK, and runs the benchmark; high technical knowledge. | Agent interfaces, SDK, documentation |
| AI agent | agent key | Non-human system actor that issues tool calls; treated as untrusted once it has read untrusted content. | MCP, `/v1` endpoints |
| Business user | none | Employee who asks the agent for help; never uses Mirsad directly but sees the explanation when an action is blocked. | Through the agent |
| Attacker | none | Misuse actor who controls content the agent reads; has no access to the gateway, its configuration or its secrets. | None |

## 2.4 Operating environment

Table: Operating environment {#tab:d3-env widths=1.4,4.6}
| Component | Environment |
|---|---|
| Gateway server | Python 3.11 or later (developed and tested on 3.12) on Linux or macOS; one Uvicorn process; CPU only, no GPU required. Default address 127.0.0.1:8700. |
| Database | SQLite file in the data directory (default) or PostgreSQL (the Compose file uses PostgreSQL 16). |
| Container deployment (optional) | Docker image and Docker Compose stack with the gateway and PostgreSQL, plus an optional profile with Ollama for the demonstration agent. |
| Web clients | Current desktop and mobile browsers with service workers, the Fetch streams API and notifications; Android browsers; iOS and iPadOS 16.4 or later, where push notifications require the PWA to be added to the Home Screen [@eidson2023-webpush]. |
| Web build tools | Node.js 20.19 or later to build the dashboard and approver app. |
| Agents | Any MCP client (stdio or streamable HTTP) or any client of the OpenAI chat-completions API with tool calling; Python programs through the SDK. |
| Demonstration LLM | Ollama serving Qwen2.5-7B-Instruct on the same machine or network [@ollama-repo; @qwen2024qwen25_7b_card]. |

## 2.5 Design and implementation constraints

- **Standard protocols only.** The gateway must work with any LLM vendor (NFR2); it uses MCP and OpenAI-style JSON and no vendor-specific SDK in the decision path. The official MCP Python SDK version 2 is used, and all protocol code is kept in the adapter package so that protocol changes stay local.
- **CPU-only detection.** The detector is a character and word n-gram linear model combined with weighted rules, so that it runs within the latency budget on hardware without a GPU. Model weights are stored as NumPy arrays and JSON metadata and loaded without pickle.
- **Fail-closed behaviour.** If a decision layer, the detector or the audit log fails, the call is denied or the result blocked; a call that cannot be audited is not executed.
- **Portable persistence.** Only column types supported by both SQLite and PostgreSQL are used. Rate-limit counters are kept in memory per process, so running several gateway replicas is out of scope.
- **Bounded user input.** Regular expressions in policies are checked to limit denial-of-service risk, and request bodies are limited to 1 MB.
- **Bilingual output.** Every message that can reach an approver or administrator exists in English and Arabic, and the user interfaces support right-to-left layout.
- **OpenAI-compatible endpoint is non-streaming.** Requests with `stream=true` are rejected.
- **Regulation and ethics.** Personal identifiers are masked in logs in line with the PDPL [@ksa2021pdpl]; controls are aligned with the NCA Essential Cybersecurity Controls [@nca2024ecc]; demonstration and benchmark data is synthetic and uses reserved `.example` domains.
- **Data authorship.** Attack-labelled detector data and benchmark attack files are written and reviewed by the team, not by the AI assistant used during development, so these inputs are not produced automatically.
- **Project limits.** Two academic semesters, five students and the revised budget of 1,185 SAR set out in D2. The software is released under the Apache-2.0 licence.

## 2.6 User documentation

The release includes the D6 Software User Guide (installation, administration and the approver workflow), component guides under `docs/` for developers and integrators, an OpenAPI description of the REST API served at `/openapi.json`, and `--help` text for every command of the `mirsad` CLI.

## 2.7 Assumptions and dependencies

**Assumptions.** If any of these does not hold, some requirements cannot be met.

- AS-1: Agents can reach the protected tools only through Mirsad. The deploying organisation enforces this through network and credential configuration; a direct path to a tool bypasses every control.
- AS-2: The policy correctly describes each tool's trust, sensitivity, sink and risk, and lists all of the organisation's internal domains.
- AS-3: The server secret (used to sign JWTs and to derive the audit HMAC key) is kept from attackers and from insiders who can write to the database.
- AS-4: Approvers are reachable within the approval timeout (120 seconds by default); otherwise requests expire and the calls are denied.
- AS-5: Any deployment reachable from other machines terminates TLS in front of the gateway.
- AS-6: Attackers can influence only content that the agent reads; they cannot change the agent, its system prompt, the gateway or its configuration (the threat model of the final report, Section 3.2).

**Dependencies.**

- DP-1: The MCP specification [@mcp2026spec] and the official MCP Python SDK version 2.
- DP-2: Ollama and the Qwen2.5-7B model for the demonstration agent and LLM benchmark runs.
- DP-3: Browser push services, including Apple's for iOS, for Web Push delivery.
- DP-4: Team-authored labelled data for detector training and for benchmark attack episodes.
- DP-5: Third-party open-source libraries, monitored by dependency vulnerability scans.

# 3 Specific Requirements

This section states the requirements that the delivered system must satisfy. Identifiers are used throughout the project documents: FRx.y for functional requirements, NFRn for non-functional requirements, BRn for business rules, UC-nn and MC-nn for use cases and misuse cases, IF-UI-nn, IF-SW-nn and IF-CO-nn for external interface requirements, and DR-nn for data requirements. Interface and data requirements refine the functional and non-functional requirements named in their last column, so they are traced through them.

## 3.1 Functional and Non-Functional Requirements

<<include docs/report/content/parts/requirements_fr_nfr.md>>

## 3.2 Use Cases

<<include docs/report/content/parts/usecases.md>>

## 3.3 External Interface Requirements

### 3.3.1 User interfaces

Table: User interface requirements {#tab:d3-ui widths=0.8,4.2,1.0}
| ID | Requirement | Refines |
|---|---|---|
| IF-UI-01 | The administration dashboard shall be served at `/` as a single-page application with the pages Login, Overview, Activity (audit log), Approvals, Policies, Agents, Users, Tools, Detector Playground, Demo Console and Settings. | FR6.2, FR7.1, FR7.2 |
| IF-UI-02 | The approver application shall be served at `/approve` as an installable PWA with a web app manifest and a service worker [@w3c_appmanifest; @w3c_serviceworkers]. It shall list pending requests with a risk colour and a countdown, and its detail view shall show the plain-language summary, why the call was paused, where the data came from, the raw arguments (collapsed by default) and Approve and Deny buttons that ask for confirmation. | FR5.2, FR5.3, NFR4 |
| IF-UI-03 | Both interfaces shall offer English and Arabic through a language toggle, with a right-to-left layout for Arabic. | NFR4 |
| IF-UI-04 | Both interfaces shall be operable by keyboard, label every control, meet WCAG 2.2 AA contrast, avoid colour-only signals and honour reduced-motion and light or dark preferences [@w3c2023wcag22]. | NFR10 |
| IF-UI-05 | The dashboard and the approver app shall update from the server event stream without a page reload. | FR5.2, FR7.2 |
| IF-UI-06 | The Policies page shall validate YAML with line-numbered errors, show the difference from the active version and require confirmation before activation. | FR2.1, FR2.5 |
| IF-UI-07 | An agent API key shall be displayed only once, when it is created or rotated. | FR7.1, NFR3 |
| IF-UI-08 | The `mirsad` CLI shall provide the commands `serve`, `init`, `policy validate`, `policy activate`, `audit verify`, `audit export`, `audit replay`, `scan`, `agent create`, `user create`, `mcp-proxy` and `detector train`. | FR2.5, FR6.1, FR6.3, FR7.1 |

### 3.3.2 Software interfaces

Table: Software interface requirements {#tab:d3-sw widths=0.8,1.3,2.7,1.0}
| ID | Interface | Requirement | Refines |
|---|---|---|---|
| IF-SW-01 | MCP server for agents | Mirsad shall act as an MCP server [@mcp2026spec] over stdio (`mirsad mcp-proxy`) and streamable HTTP at `/mcp`. `tools/list` returns only the tools the agent's policy allows; every `tools/call` passes through the gateway; a denied call returns an MCP tool error whose text explains the block in English and Arabic. Agents authenticate with `Authorization: Bearer mk_...` or `X-Mirsad-Key`. | FR1.1, FR1.4, FR2.4 |
| IF-SW-02 | MCP client to upstream tools | Mirsad shall connect to upstream tool servers over stdio, streamable HTTP or in-process, as configured in `configs/upstreams.yaml`, and shall also accept plain Python functions registered as tools. | FR1.1, FR8.1 |
| IF-SW-03 | OpenAI-compatible API | `POST /v1/chat/completions` shall accept the chat-completions format, inspect every `tool` message before forwarding it, check every returned `tool_calls` entry, remove denied calls and append an explanation. The session is taken from the `X-Mirsad-Session` header or derived from the first user message. Requests are forwarded to the configured LLM base URL, by default a local Ollama server [@ollama-openai-compat]. | FR1.2, NFR2 |
| IF-SW-04 | Guard API | `POST /v1/guard/tool-call`, `POST /v1/guard/tool-result`, `POST /v1/tools/{tool}/invoke` and `GET /v1/tools` shall return a decision, an inspection outcome, a combined response and the visible tool list as JSON. | FR1.3, FR1.4 |
| IF-SW-05 | Python SDK | `MirsadClient` and `AsyncMirsadClient` shall provide `check_call`, `inspect_result`, `invoke`, `tools` and a `guard` decorator that raises `MirsadBlocked` when a call is denied. | FR1.3 |
| IF-SW-06 | Administration REST API | Endpoints under `/api/` shall exchange JSON, return errors as `{"detail": ...}` without echoing submitted values, and be described by OpenAPI at `/openapi.json`. Humans authenticate with HS256 JSON Web Tokens [@rfc7519]; access is limited by the roles admin, approver and auditor. Agent keys are rejected on `/api/` and user tokens on `/v1/`. | FR5.3, FR6.2, FR7.1, NFR3 |
| IF-SW-07 | Database | Persistence shall go through SQLAlchemy 2.0 to SQLite or PostgreSQL, selected by the database URL, with the same code and schema on both. | NFR5, NFR11 |
| IF-SW-08 | LLM backend | The demonstration agent and the OpenAI-compatible proxy shall reach the model only through an OpenAI-compatible API whose base URL, model name and key are settings. | FR8.1, NFR2 |

### 3.3.3 Communications interfaces

Table: Communications interface requirements {#tab:d3-comms widths=0.8,4.2,1.0}
| ID | Requirement | Refines |
|---|---|---|
| IF-CO-01 | The gateway shall serve HTTP. Deployments reachable from other machines shall be served over HTTPS through a TLS-terminating proxy or tunnel, and the gateway adds HSTS when the request arrived over HTTPS. The approver PWA requires a secure context, because service workers run only over HTTPS, with `localhost` treated as secure for development [@mdn-service-worker]. | NFR3, FR5.3 |
| IF-CO-02 | Every response shall carry a Content Security Policy restricted to the server's own origin (the interactive API documentation pages have their own, wider policy), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`; API responses shall carry `Cache-Control: no-store`. Request bodies over 1 MB, declared or streamed, shall be rejected with HTTP 413. Cross-origin requests shall be accepted only from configured origins. | NFR3 |
| IF-CO-03 | `GET /api/stream` shall deliver Server-Sent Events named `approval.requested`, `approval.decided` and `audit.event` with JSON data. Clients read the stream with `fetch`, so the token is sent in the `Authorization` header and never in a URL, and they reconnect with back-off. Hosting paths without SSE support, such as Cloudflare Quick Tunnels [@cloudflare-quick-tunnels], are not supported for the approval channel. | FR5.2, FR7.2, NFR3 |
| IF-CO-04 | When a VAPID key pair is configured, the server shall send approval notifications through the browsers' push services. Browsers register at `POST /api/push/subscribe` using the public key from `GET /api/push/vapid` and leave at `POST /api/push/unsubscribe`; subscriptions that the push service reports as gone (HTTP 404 or 410) are deleted. Without VAPID keys Web Push is disabled and the event stream still delivers requests. | FR5.2, NFR4 |
| IF-CO-05 | Agent traffic shall use MCP over stdio or streamable HTTP, or JSON over HTTP for the OpenAI-compatible and Guard endpoints. Agent credentials shall travel only in request headers. | FR1.1–FR1.3, NFR3 |

## 3.4 Data Requirements

### 3.4.1 Data entities and retention

@tab:d3-data lists the data that Mirsad stores or holds and how long it is kept in version 1.0. The relational tables are designed in detail in D4.

Table: Data entities and retention {#tab:d3-data widths=1.2,2.4,0.9,1.9}
| Entity | Main attributes | Created by | Retention |
|---|---|---|---|
| User (`users`) | Username, salted scrypt password hash [@rfc7914], role, display name, language, disabled flag | Administrator (API or CLI) | Until an administrator deletes it. Audit events and approval records keep the username as text, so deleting a user does not remove attribution. |
| Agent (`agents`) | Identifier, name, description, policy agent identifier, key prefix, SHA-256 hash of the key, created and last-seen times, disabled flag | Administrator | Until deleted. The full key is shown once and never stored. |
| Policy version (`policies`) | SHA-256 version identifier, YAML text, created at and by, active flag, comment | Administrator, or the first start-up | Kept indefinitely, because replaying a stored decision needs its exact policy version. |
| Audit event (`audit_events`) | Sequence number, timestamp, event type, session, agent, tool, call identifier, action, risk, policy version, redacted payload of at most 20,000 characters, previous hash, hash | Gateway and API | Append-only; no role can edit or delete events through the application (BR6). Version 1.0 has no purge function; the deploying organisation sets the retention period and archives through JSON or CSV export. |
| Approval (`approvals`) | Identifier, created and expiry times, status (pending, approved, denied, expired, cancelled), agent, session, call, tool, redacted arguments, decision, English and Arabic summaries, risk, decided by and at, note | Gateway | Kept with the audit log; each request and decision is also an audit event. |
| Push subscription (`push_subscriptions`) | User, endpoint, `p256dh` and `auth` keys, created time | Approver's browser | Until unsubscribed or reported gone by the push service. |
| Taint session state (memory only) | Per session: identifying values with source tool, call and field; whether untrusted content was read and whether an injection was detected | Gateway | Not persisted. At most 2,000 values per session; a session idle for 6 hours is dropped; all state is lost on restart. A minimal snapshot is stored in each decision's audit payload for replay. |
| Detector dataset and model (files) | JSONL records with text, label, language, variety, carrier, attack type, difficulty and source; model weights and metadata | Team; training script | Versioned in the repository; provenance documented in a datasheet [@gebru2021datasheets]. |
| Evidence reports (files under `reports/`) | Test, coverage, scan, latency and benchmark results; `results_summary.json` | Evidence scripts | Regenerated for each deliverable and kept with the release. |
| Secrets | Server secret (signs JWTs; the audit HMAC key is derived from it), VAPID key pair, database password | Operator | Environment variables, or a generated file in the data directory readable only by its owner; never logged or exported. |

### 3.4.2 Data integrity, protection and quality

Table: Data requirements {#tab:d3-dr widths=0.6,4.4,1.0}
| ID | Requirement | Refines |
|---|---|---|
| DR-01 | Each audit event shall store `hash = HMAC-SHA-256(key, prev_hash + "\|" + canonical JSON of the event)`, where canonical JSON has sorted keys and no whitespace and the first event uses a previous hash of 64 zeros [@rfc2104]. Verification shall report the first sequence number at which the chain breaks. | FR6.1, NFR7 |
| DR-02 | Before an event is hashed and stored, secrets (API keys, bearer tokens, JWTs, private keys and fields named like passwords, secrets or tokens) shall be removed, and payment-card numbers, Saudi national identity numbers and IBANs shall be masked. Approval arguments shall be redacted in the same way. | FR6.1, NFR8 |
| DR-03 | Passwords shall be stored only as salted scrypt hashes and agent keys only as SHA-256 hashes; no API shall return either. | NFR3 |
| DR-04 | Timestamps shall be stored as UNIX epoch seconds. | NFR7 |
| DR-05 | Demonstration and benchmark data shall be synthetic: a fictional company, reserved `.example` domains and invented phone numbers, IBANs and identifiers. | NFR8 |
| DR-06 | Detector records shall follow the schema in `docs/detector.md`. Training, validation and test splits shall be separated by authoring batch so that no test text appears in training, and the dataset build shall report a leakage check. | FR4.1 |
| DR-07 | Stored policy versions shall be immutable; activating an earlier version shall re-use its stored text and identifier. | FR2.5, FR6.3 |

# 4 Verification

## 4.1 Verification methods

Each requirement is verified by one or more of the four methods of ISO/IEC/IEEE 29148 [@iso29148_2018]: **test** (an automated or scripted check with an expected result), **demonstration** (operating the system and observing the behaviour), **analysis** (measurement or calculation from data) and **inspection** (review of code, configuration or documents against a checklist). Automated tests are preferred, because they are repeated on every change. All measured values below are read from `reports/results_summary.json`, which `scripts/run_evidence.sh` regenerates from the test runs, scans and benchmarks.

## 4.2 Verification by requirement class

Table: Verification of each requirement class {#tab:d3-verification widths=1.3,0.8,2.2,1.9}
| Requirement class | Method | How it is verified | Current evidence |
|---|---|---|---|
| FR1 Interception and adapters | Test, demonstration | Adapter tests with real MCP clients over stdio and HTTP; OpenAI-compatible proxy and SDK tests; demonstration agent running through the gateway | {{reports/results_summary.json#python_tests.by_area.adapters}} adapter tests and {{reports/results_summary.json#python_tests.by_area.integration}} integration tests pass |
| FR2 Policy, BR1–BR5 | Test | Passing and violating cases for each constraint operator; rate-limit windows; deny-overrides; scenario tests for the business rules; hot reload | {{reports/results_summary.json#python_tests.by_area.policy}} policy tests pass |
| FR3 Taint tracking | Test | Rules fire on fixtures that model exfiltration flows and stay silent on benign counterparts such as replying to the sender | {{reports/results_summary.json#python_tests.by_area.taint}} taint tests pass |
| FR4 Detector | Test, analysis | Unit tests of normalisation, rules, sanitising and spotlighting; precision, recall and F1 on held-out English and Arabic test sets | {{reports/results_summary.json#python_tests.by_area.detector}} detector tests pass; F1 English {{reports/results_summary.json#detector.splits.test_en.f1|.2f}}, Arabic {{reports/results_summary.json#detector.splits.test_ar.f1|.2f}} (target 0.85) |
| FR5 Approval | Test, demonstration | Approval-service tests (expiry, double decision), API tests, web tests, approval round trip on a phone | Approval tests within the {{reports/results_summary.json#python_tests.by_area.audit}} audit-area tests; {{reports/results_summary.json#web_tests.total}} web tests ({{reports/results_summary.json#web_tests.files}} Vitest suites in 10 test files) pass |
| FR6 Audit, BR6, DR-01, DR-02 | Test | Tamper tests (modify, delete, reorder); query and export tests; redaction tests; replay of every decision after each benchmark run | {{reports/results_summary.json#bench.scripted_benign_oracle.replay_matched}} of {{reports/results_summary.json#bench.scripted_benign_oracle.replay_checked}} decisions replayed to the same action in one scripted run and {{reports/results_summary.json#bench.scripted_benign_deny.replay_matched}} of {{reports/results_summary.json#bench.scripted_benign_deny.replay_checked}} in the other |
| FR7 Administration, IF-SW-06 | Test | API tests including role checks for each endpoint; UI tests | {{reports/results_summary.json#python_tests.by_area.api}} API tests pass |
| FR8 Demonstration and benchmark | Test, demonstration | Demonstration scenarios in protected and unprotected modes; benchmark runs for every defence configuration | {{reports/results_summary.json#python_tests.by_area.demo}} demo and {{reports/results_summary.json#python_tests.by_area.bench}} benchmark tests pass; {{reports/results_summary.json#bench.scripted_benign_oracle.tasks}} benign tasks per scripted run |
| NFR1 Performance | Analysis | Latency benchmark: {{reports/results_summary.json#latency.separate_process.calls|,}} calls, sequential and with concurrent sessions, server in a separate process | Median added latency {{reports/results_summary.json#latency.separate_process.sequential_added_p50|.1f}} ms sequential, {{reports/results_summary.json#latency.separate_process.concurrent_added_p50|.0f}} ms with {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions (target 200 ms) |
| NFR2 Interoperability | Test, demonstration | Adapter tests with MCP clients and with the OpenAI-compatible proxy; an LLM agent that reaches a local model through the OpenAI-compatible API and calls tools through the gateway | Adapter tests (see FR1); LLM smoke run with {{reports/results_summary.json#bench.llm_smoke.tasks}} tasks, audit chain intact |
| NFR3 Security, IF-CO-01–05 | Test, analysis | Security test suite; static analysis; dependency scans; penetration test (T6.4) | {{reports/results_summary.json#python_tests.by_area.security}} security tests pass; {{reports/results_summary.json#security.bandit_issues}} Bandit issues; {{reports/results_summary.json#security.pip_audit_vulnerable}} vulnerable Python packages of {{reports/results_summary.json#security.pip_audit_packages}}; {{reports/results_summary.json#security.npm_audit_vulnerabilities}} npm findings |
| NFR4 Usability, IF-UI-02, IF-UI-03 | Analysis, inspection | Keystroke-Level Model estimate of the approval task [@card1980klm], a task walkthrough and a user study | Partially verified: KLM estimate completed (final report, Section 4.2.8: 21.9 s and 28.8 s reading the summary, 44.1 s reading every reason of a multi-reason request); user study pending |
| NFR5 Deployability | Demonstration | Native installation and start-up; `docker compose up` on a machine with Docker | Partially verified: native installation used for all measurements; Docker deployment not yet executed |
| NFR6 Reliability | Test | Expiry leads to denial; tool failures are reported safely; failures of the audit log or detector fail closed | Within the API and audit-area tests |
| NFR7 Accountability, DR-04 | Inspection, test | Audit event schema review; replay | See FR6 |
| NFR8 Privacy, DR-02, DR-05 | Test, inspection | Redaction unit tests; review of demonstration data | Within the audit-area tests |
| NFR9 Maintainability | Analysis | Statement coverage of the core package; linting | {{reports/results_summary.json#coverage.percent|.1f}}% coverage (target 80%) |
| NFR10 Accessibility, IF-UI-04 | Inspection | WCAG 2.2 checklist review of both interfaces [@w3c2023wcag22] | Partially verified: contrast and accessible names tested automatically; checklist review pending (T6.1) |
| NFR11 Scalability | Analysis | Concurrent sessions in the latency benchmark | {{reports/results_summary.json#latency.separate_process.sessions}} sessions with {{reports/results_summary.json#latency.separate_process.concurrent_errors}} errors |
| Objective 3 benchmark targets | Analysis | Mirsad-Bench with scripted and LLM agents against an unprotected baseline | Benign false-positive rate {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.fpr|.1%}} (target at most 5%); ASR reduction {{reports/results_summary.json#bench.scripted_attack_oracle.configs.full.asr_reduction|.1%}} (target at least 80%) |
| DR-03, DR-06, DR-07 | Test | Authentication tests; dataset build leakage check; policy-store tests | Within the audit, detector and API tests |

Detector F1 and attack success rate are **not measured yet**. Both need attack-labelled data written by the team (Section 2.5). Once the team adds the data as described in `docs/detector.md` and `bench/scenarios/attacks/README.md`, `make detector` produces the F1 values, and the benchmark, which already executes attack episodes when attack files exist, produces the attack success rate. Until then these values are shown as pending.

The benign measurements are precise about what they cover. In the scripted benchmark with full protection, {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.fpr|.1%}} of benign calls were denied automatically and {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.friction|.1%}} were escalated to a human. With an approver who accepts legitimate requests, utility was {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.utility|.0%}}; if every escalation were denied, it would fall to {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.utility|.0%}}. The LLM run covers only {{reports/results_summary.json#bench.llm_smoke.tasks}} tasks and is a smoke test, not a utility estimate.

## 4.3 Traceability

The requirements traceability matrix (RTM) links every functional and non-functional requirement to the test cases that verify it and to their results. It is maintained with the test specification in D5 and reproduced in Appendix B of the final report. The acceptance criteria in the requirement tables of Section 3.1 define what each test must show; external interface and data requirements are traced through the FR and NFR identifiers in their "Refines" column. A change to a requirement after the M1 baseline is recorded as a backlog item and updated in this SRS, in the RTM and in the affected tests in the same sprint.

## 4.4 Open verification items

1. Train and evaluate the detector on the team's labelled data (`make detector`), then fill the FR4 row.
2. Add the team's attack files and measure the attack success rate against the unprotected baseline.
3. Run the Docker Compose deployment on a machine with Docker (NFR5).
4. Run the approval-time user study (NFR4; the Keystroke-Level Model estimate is reported in Section 4.2.8 of the final report) and the WCAG checklist review (NFR10).
5. Repeat the latency benchmark with the trained detector model, and run the LLM agent on the full task set rather than the smoke test.
