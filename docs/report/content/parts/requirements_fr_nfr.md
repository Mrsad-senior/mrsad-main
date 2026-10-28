#### Functional requirements

Functional requirements are grouped by the eight capabilities in the proposal (FR1–FR8) and refined into testable sub-requirements. Priorities use the MoSCoW scale (M = must, S = should, C = could). Each requirement has an acceptance criterion; the test cases that verify it are listed in the requirements traceability matrix (Appendix B of the final report; deliverable D5, Section B.2).

Table: Functional requirements {#tab:fr widths=0.65,3.4,0.45,2.2}
| ID | Requirement | Pri. | Acceptance criterion |
|---|---|---|---|
| FR1.1 | The gateway shall act as an MCP server towards agents and an MCP client towards upstream MCP servers over stdio and streamable HTTP, forwarding `tools/list` and `tools/call`. | M | An MCP client connected through Mirsad lists and calls upstream tools; results are identical to a direct connection when the policy allows. |
| FR1.2 | The gateway shall expose an OpenAI-compatible `/v1/chat/completions` endpoint that inspects `tool` messages before forwarding and checks returned `tool_calls`. | M | A denied tool call is removed from the response and replaced by an explanation; tool messages are sanitised. |
| FR1.3 | The gateway shall expose a Guard API (`/v1/guard/tool-call`, `/v1/guard/tool-result`, `/v1/tools/{tool}/invoke`) and a Python SDK for frameworks that execute tools themselves. | M | SDK `guard` decorator blocks a denied call by raising `MirsadBlocked`. |
| FR1.4 | Each agent shall only discover the tools its policy allows (least-privilege discovery). | S | `tools/list` and `GET /v1/tools` omit tools with `allow: false`. |
| FR2.1 | The system shall load policies written in a declarative YAML language with per-agent tool entries, glob patterns, defaults, global rules and a monitor mode. | M | All shipped policies validate; invalid documents are rejected with line-numbered messages. |
| FR2.2 | The policy engine shall evaluate per-parameter constraints (`max`, `min`, `max_length`, `enum`, `not_in`, `pattern`, `not_pattern`, `domain_in`, `domain_not_in`, `max_items`, `type`, `required`), each with a configurable violation action (deny or require approval). | M | Each operator has passing and violating test cases. |
| FR2.3 | The policy engine shall enforce sliding-window rate limits per agent and tool. | M | The (n+1)-th call inside the window is denied with code `RATE_LIMIT`. |
| FR2.4 | Reasons from all layers shall be combined with a deny-overrides algorithm, and every decision shall carry machine-readable reason codes and bilingual explanations. | M | A call with one deny reason is denied regardless of other reasons. |
| FR2.5 | Administrators shall be able to validate, activate and roll back policy versions at run time without restarting the gateway. | S | Activation hot-reloads the policy and creates a `policy.activated` audit event. |
| FR3.1 | Every tool result shall be labelled with a trust level (trusted/untrusted) and a sensitivity level (public/internal/confidential) from its tool profile. | M | The audit event for each inspection records both labels. |
| FR3.2 | The taint tracker shall record identifying values (e-mail addresses, URLs, domains, IBANs, phone numbers, identifiers and text n-grams) from results, with their source tool, call and field. | M | Values embedded in JSON and in free text are both extracted. |
| FR3.3 | The gateway shall escalate or block calls to external sinks after untrusted content was ingested, calls that carry confidential values to external sinks, and calls whose destination value originated in untrusted content. | M | The three taint rules fire on attack fixtures and do not fire when replying to a sender or e-mailing a CRM contact. |
| FR3.4 | After an injection has been detected in a session, high-risk tools shall require approval. | S | `TAINT_AFTER_INJECTION` fires for high/critical tools in that session only. |
| FR4.1 | Every untrusted tool result, and every result of a tool marked `scan` (for example CRM records), shall be scanned for embedded instructions in English, Modern Standard Arabic, Gulf dialect, Arabizi and mixed text, producing a score, label, language and highlighted spans. | M | Detector F1 ≥ 0.85 on the held-out Arabic and English test sets. |
| FR4.2 | Text shall be normalised before detection (Unicode NFKC, invisible and bidirectional control characters, Arabic diacritics and letter variants, homoglyphs), and obfuscation shall itself be reported as a signal. | M | Zero-width, homoglyph and diacritic-obfuscated payloads are detected. |
| FR4.3 | Depending on policy, detected content shall be sanitised (offending spans removed), blocked (content withheld) or flagged; untrusted content shall be spotlighted (data-marked) before reaching the model. | M | Sanitised output no longer contains the payload; spotlighting wrapper present. |
| FR5.1 | High-risk actions (payments, deletions, bulk exports, outbound messages under taint) shall be suspended and an approval request with full context created. | M | The call blocks until a decision or timeout. |
| FR5.2 | Approvers shall receive a real-time notification and a plain-language Arabic/English summary that explains what the agent wants to do, why it was paused and where the data came from. | M | Summary mentions the tool, destination and source of tainted data. |
| FR5.3 | Approvers shall approve or deny from a mobile application with an optional note; requests not decided before the timeout shall expire and be denied (fail-safe). | M | Expired requests resolve to DENY; double decisions are rejected. |
| FR6.1 | Every intercepted event shall be appended to an HMAC-SHA-256 hash-chained audit log with secrets and personal identifiers masked. | M | Verification detects modification, deletion and reordering of events. |
| FR6.2 | Users shall search, filter, view and export (CSV/JSON) audit events in the dashboard. | M | Filters by agent, tool, action, type, session, time and text return correct pages. |
| FR6.3 | Any stored decision shall be replayable: the system re-evaluates it with the stored policy version and inputs and reports whether the outcome matches. | M | 100% of benchmark decisions replay to the same action. |
| FR7.1 | Administrators shall manage agents and their API keys (create, rotate, disable), users and roles (admin, approver, auditor), policies and tool registrations. | M | API keys are shown only once and stored hashed. |
| FR7.2 | The dashboard shall show live statistics (calls, blocked, approvals, detections, latency) and a detector playground. | S | Overview reflects new events without reload (SSE). |
| FR8.1 | The system shall ship a simulated enterprise workspace (e-mail, CRM, web, documents, payments) exposed as an MCP server and a demonstration LLM agent. | M | Demo scenarios run in protected and unprotected modes. |
| FR8.2 | The system shall ship Mirsad-Bench, a reproducible benchmark harness with English and Arabic scenarios, ablation configurations and metric reports. | M | One command (`scripts/run_bench.sh`) reproduces the benchmark result tables of the evaluation (final report, Chapter 4; deliverable D5, Section B.5). |

#### Non-functional requirements

Table: Non-functional requirements {#tab:nfr widths=0.7,1.1,3,2}
| ID | Quality attribute | Requirement | Measure / verification |
|---|---|---|---|
| NFR1 | Performance | Median added latency ≤ 200 ms per tool call, excluding time waiting for a human. | Latency benchmark over 1,000 HTTP calls (p50, p95, p99). |
| NFR2 | Interoperability / portability | Model-agnostic: no dependency on a specific LLM provider; standard protocols only (MCP, OpenAI-style JSON). | Same gateway used by an MCP client and by an OpenAI-compatible agent backed by a local model. |
| NFR3 | Security | Agents authenticate with API keys (stored as SHA-256 hashes) and humans with JWTs and role-based access; secrets are never logged; audit integrity is verifiable; security headers, body-size limits and login throttling are applied. | Security test suite (Section 4.2.6 of the final report), redaction tests, SAST and dependency scans. |
| NFR4 | Usability | An approver can understand and decide on a request in under 30 seconds on a phone; UI available in Arabic (RTL) and English. | Keystroke-Level Model estimate and task walkthrough. |
| NFR5 | Deployability | Deployable with a single `docker compose up` (or one script without Docker). | Deployment guide (Appendix E); local run script verified. |
| NFR6 | Reliability / fail-safe | If the approver does not respond, the call is denied; internal errors in a tool never crash the gateway and are reported to the agent safely. | Expiry and executor-failure tests. |
| NFR7 | Accountability | Every allowed, denied or approved action is attributable to an agent, session, policy version and (for approvals) a named human. | Audit event schema; replay test. |
| NFR8 | Privacy | Personal identifiers (national ID, IBAN, card numbers) are masked in logs; demo data is synthetic. | Redaction unit tests. |
| NFR9 | Maintainability | Modular layers with typed interfaces, ≥ 80% statement coverage of the core package, linted code, documented APIs. | Coverage report, Ruff, OpenAPI docs. |
| NFR10 | Accessibility | Dashboard and approval app follow WCAG 2.2 AA basics: keyboard navigation, labels, contrast ≥ 4.5:1, no colour-only signals, reduced motion. | UI review checklist. |
| NFR11 | Scalability (bounded) | Single node handles ≥ 50 concurrent agent sessions; state is in a relational database (SQLite in development, PostgreSQL in deployment). | Concurrency test in the latency benchmark. |

#### Business rules and constraints

- BR1: Unknown agents and tools not mentioned in the policy are denied (default-deny).
- BR2: Payments and record deletions always require human approval, whatever the risk score.
- BR3: No more than 50 customer records may be exported or e-mailed in one call.
- BR4: E-mail to domains outside the organisation requires approval; data originating from untrusted content may never choose its own destination.
- BR5: An approval request expires after 120 seconds (configurable) and expiry means denial.
- BR6: Audit events are append-only; no user role can edit or delete them through the application.
