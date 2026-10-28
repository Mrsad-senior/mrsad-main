@fig:usecase shows the actors and use cases. Besides the four human roles (approver, administrator, auditor and agent developer) the AI agent is modelled as a system actor, and the attacker is modelled as a *misuse actor* following the misuse-case technique: each misuse case is linked to the use case it threatens and to the security use case that mitigates it.

![Use-case diagram with misuse cases (black) and the security use cases that mitigate them](docs/figures/usecase.png){#fig:usecase width=6.0}

Table: Use-case catalogue {#tab:uc widths=0.6,1.8,1.1,3}
| ID | Use case | Primary actor | Summary |
|---|---|---|---|
| UC-01 | Invoke tool via gateway | AI agent | The agent calls a tool; Mirsad authenticates the agent, evaluates policy, rate limits and taint, possibly asks for approval, executes the call and returns the inspected result. |
| UC-02 | Receive inspected result | AI agent | Mirsad scans the tool result, sanitises or blocks injected instructions, labels trust and sensitivity, and returns spotlighted content. |
| UC-03 | Discover permitted tools | AI agent | The agent lists tools and sees only those allowed for it. |
| UC-04 | Integrate agent | Agent developer | Connect an agent through the MCP proxy, the OpenAI-compatible endpoint or the SDK. |
| UC-05 | Approve / deny action | Approver | Review a pending high-risk action on the phone and decide. |
| UC-06 | Receive push alert | Approver | Get a real-time notification when an action is paused. |
| UC-07 | View approval history | Approver | Review past decisions and notes. |
| UC-08 | Manage policies | Administrator | Edit, validate, activate or roll back the YAML policy. |
| UC-09 | Manage agents and keys | Administrator | Register agents, issue, rotate and revoke API keys. |
| UC-10 | Manage users and roles | Administrator | Create approvers, auditors and administrators. |
| UC-11 | Test detector | Administrator | Paste Arabic or English text and see the detector's score and highlighted spans. |
| UC-12 | Monitor dashboard and demo | Administrator | Watch live statistics; run the demonstration agent in protected and unprotected modes. |
| UC-13 | Search and export audit log | Auditor | Filter events and export evidence. |
| UC-14 | Verify audit integrity | Auditor | Recompute the HMAC hash chain and locate any tampering. |
| UC-15 | Replay a decision | Auditor | Re-evaluate a stored decision with its stored policy version and inputs. |
| UC-16 | Run Mirsad-Bench | Agent developer | Reproduce the evaluation with scripted or LLM agents and ablations. |
| MC-01 | Plant hidden instructions | Attacker | Place instructions in an e-mail, web page, document or CRM note the agent will read (mitigated by UC-02). |
| MC-02 | Hijack agent to exfiltrate | Attacker | Make the agent send confidential data or money to the attacker (mitigated by UC-01 policy, taint and approval). |
| MC-03 | Tamper with audit log | Attacker / insider | Modify or delete audit records to hide an incident (mitigated by UC-14). |

@tab:uc01, @tab:uc05, @tab:uc08 and @tab:uc14 specify the four core use cases.

Table: Use-case specification UC-01 – Invoke tool via gateway {#tab:uc01 widths=1.2,5}
| Field | Description |
|---|---|
| Actors | AI agent (primary); Approver (secondary, only when escalated) |
| Preconditions | The agent is registered and holds a valid API key; an active policy exists; the upstream tool server is reachable. |
| Trigger | The agent's model emits a tool call (MCP `tools/call`, an OpenAI `tool_calls` entry, or a Guard API request). |
| Main flow | 1. Adapter authenticates the agent key and builds a `ToolCall`. 2. Policy engine resolves the tool profile, checks that the tool is allowed, evaluates parameter constraints, rate limits and global rules, and resolves the sink. 3. Taint tracker evaluates the call against the session's provenance state. 4. Gateway combines reasons (deny-overrides) and computes the risk score. 5. The decision is appended to the audit log. 6. The call is forwarded to the upstream tool. 7. UC-02 inspects the result. 8. The inspected result is returned to the agent. |
| Alternative flows | A1 (deny): at step 4 the action is DENY; the agent receives a bilingual explanation and the call never reaches the tool. A2 (approval): at step 4 approval is required; UC-05 is triggered and the call waits; approved → continue at 6, denied or expired → A1. A3 (monitor mode): the would-be decision is logged but the call is always forwarded. |
| Exceptions | E1 invalid key → HTTP 401, audited as authentication failure; E2 upstream error → error result returned to the agent and audited; E3 request larger than 1 MB → HTTP 413. |
| Postconditions | Exactly one `tool_call.decision` event (and, if executed, one `tool_result.inspection` event) exists in the hash chain for the call. |
| Requirements | FR1.1–FR1.3, FR2.1–FR2.4, FR3.3, FR5.1, FR6.1, NFR1, NFR3 |

Table: Use-case specification UC-05 – Approve / deny action {#tab:uc05 widths=1.2,5}
| Field | Description |
|---|---|
| Actors | Approver (primary) |
| Preconditions | The approver is logged in to the approval app (role approver or admin); a request is pending. |
| Trigger | The gateway escalates a call (REQUIRE_APPROVAL) and publishes `approval.requested`. |
| Main flow | 1. The app shows a notification and adds the request to the pending list with a risk badge and a countdown. 2. The approver opens it and reads the plain-language summary ("what", "why paused", "where the data came from"). 3. The approver optionally expands the raw arguments. 4. The approver taps Approve or Deny, optionally adds a note, and confirms. 5. The server records the decision, resumes the waiting call and audits `approval.decided`. |
| Alternative flows | A1: the request expires before step 4 → status EXPIRED, the call is denied. A2: another approver decides first → the app refreshes and shows the outcome. |
| Postconditions | The approval record stores the decision, the approver's username, the time and the note. |
| Requirements | FR5.1–FR5.3, NFR4, NFR6, NFR7 |

Table: Use-case specification UC-08 – Manage policies {#tab:uc08 widths=1.2,5}
| Field | Description |
|---|---|
| Actors | Administrator |
| Preconditions | Logged in with role admin. |
| Main flow | 1. Open the Policies page; the active YAML and version history are shown. 2. Edit the YAML. 3. Press Validate; errors are listed with line numbers. 4. Review the diff against the active version. 5. Press Activate and confirm. 6. The new version is stored, the gateway hot-swaps its policy and `policy.activated` is audited. |
| Alternative flows | A1: validation fails → activation disabled. A2: roll back by activating an earlier version. A3: switch to `mode: monitor` to trial a policy without enforcement. |
| Requirements | FR2.1, FR2.5, FR7.1 |

Table: Use-case specification UC-14 – Verify audit integrity {#tab:uc14 widths=1.2,5}
| Field | Description |
|---|---|
| Actors | Auditor or administrator |
| Main flow | 1. Press "Verify chain" (or run `mirsad audit verify`). 2. The server recomputes the HMAC of every event in sequence order and compares it with the stored hash and the next event's `prev_hash`. 3. The result shows the number of events checked, the head hash, and either "intact" or the first sequence number where the chain breaks. |
| Postconditions | An `audit.verified` event records the check. |
| Requirements | FR6.1, FR6.3, NFR3, NFR7 |
