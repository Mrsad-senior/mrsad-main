# Chapter 1 – Introduction

## 1.1 Background

Large language models (LLMs) have moved quickly from conversational assistants to *agents*: software that receives a goal in natural language, plans a sequence of steps, and carries those steps out by calling tools. A modern agent can read a mailbox, search a customer relationship management (CRM) system, open web pages and documents, call internal APIs, send messages and even initiate payments. Two technical developments made this practical. The first is native *function calling*, in which the model emits a structured request (a tool name plus JSON arguments) that the host application executes and whose result is fed back to the model, following the reason-and-act loop popularised by ReAct [@yao2023react] and tool-learning work such as Toolformer [@schick2023toolformer]. The second is the Model Context Protocol (MCP) [@mcp2026spec], an open protocol that standardises how agents discover and invoke tools hosted by independent servers, so the same agent can be connected to many enterprise systems without bespoke integration code.

This capability creates a new security problem. An agent treats everything placed in its context window as potential instructions, including the *content returned by its tools*. If an attacker can influence any of that content, for example by sending an e-mail to the organisation, editing a public web page, uploading a CV, or writing a product review, the attacker can embed instructions that the agent may follow as if they came from its user. This class of attack, *indirect prompt injection*, was first demonstrated against real LLM-integrated applications by Greshake et al. [@greshake2023indirect] and is ranked first (LLM01) in the OWASP Top 10 for LLM Applications [@owasp2024llmtop10]. Standardised benchmarks such as AgentDojo [@debenedetti2024agentdojo] and InjecAgent [@zhan2024injecagent] have since shown that tool-using agents built on leading models remain vulnerable, and that the risk is greatest when three ingredients are present together: access to private data, exposure to untrusted content, and the ability to communicate externally [@willison2025trifecta].

The Kingdom of Saudi Arabia is investing heavily in artificial intelligence under Vision 2030 [@ksa2016vision2030], with the Saudi Data and AI Authority (SDAIA) issuing AI ethics principles [@sdaia2025aiethics] and the National Cybersecurity Authority (NCA) mandating the Essential Cybersecurity Controls (ECC) for national entities [@nca2024ecc]. Banks, government service providers and customer-support centres in the Kingdom serve their customers largely in Arabic, so the agents they adopt will need to read and write Arabic. Two facts make this context distinctive. First, the Personal Data Protection Law (PDPL) [@ksa2021pdpl] makes unauthorised disclosure of personal data, exactly the outcome of a successful exfiltration attack, a regulatory violation. Second, almost all published prompt-injection defences and benchmarks are English-centric, while research on multilingual jailbreaks shows that safety measures trained mainly on English degrade on other languages, scripts and transliterations [@yong2023lowresource; @deng2024multilingual; @alghanim2024arabizi].

**Mirsad** (Arabic مرصاد, "watchtower" or "observation post") is our response: a runtime security gateway that sits between an agent and its tools, inspects every tool call and every tool result, and enforces the organisation's security policy at the point where the agent acts on the world.

## 1.2 Problem Statement

Organisations that connect LLM agents to business systems currently have no practical, language-aware control point that can stop a hijacked agent from *acting* on injected instructions. The problem has four parts.

1. **Conventional controls cannot see the attack.** The malicious instruction travels as ordinary data (an e-mail body, a web page) and the harmful action is issued by an authorised agent using valid credentials. Web application firewalls, identity and access management and data-loss prevention tools observe legitimate traffic and therefore do not intervene.
2. **Most defences classify text instead of governing actions.** Prompt-injection classifiers and guardrail frameworks operate at the model boundary and produce a probability that a text is malicious. A classifier that misses a novel phrasing provides no further protection, and none of these tools expresses rules such as "this agent may read the CRM but may never export more than 50 records" or "never e-mail data that came from the CRM to an external domain".
3. **Architectural defences are hard to adopt.** Research designs that separate trusted control flow from untrusted data, such as CaMeL [@debenedetti2025camel] and the design patterns of Beurer-Kellner et al. [@beurerkellner2025designpatterns], are strong but require the agent to be rebuilt around a specific architecture, which is unrealistic for organisations that buy or reuse agents.
4. **Arabic is largely untested.** Detectors and benchmarks are trained and evaluated almost exclusively on English, leaving Modern Standard Arabic, Gulf dialect, Arabizi and mixed Arabic-English injections without measured protection.

The project therefore asks: *can a drop-in gateway, placed at the standard tool-calling boundary and requiring no change to the agent, measurably reduce the success of indirect prompt-injection attacks in Arabic and English while keeping legitimate work flowing, adding little latency, and leaving an auditable record of every decision?*

## 1.3 Project Objectives

The proposal (SPAP form) listed six objectives, O1–O6. Following the report template, they are consolidated below into three SMART objectives; the original objectives each one covers are shown in brackets, and the measurable targets are the success criteria agreed in the proposal.

1. **Enforce action-level security at the tool boundary (O1, O2, O3).** By milestone M5 (March 2027), deliver a model-agnostic gateway that intercepts 100% of the tool calls and tool results of agents that use MCP (stdio and HTTP) or OpenAI-style function calling. The gateway enforces a declarative YAML policy with per-tool and per-parameter constraints and rate limits, uses taint tracking to block or escalate flows of untrusted or confidential data to external destinations, and adds a median latency of no more than 200 ms per tool call.
2. **Detect injected instructions in Arabic and English (O4).** By milestone M4 (February 2027), build a bilingual (Modern Standard Arabic, Gulf dialect, Arabizi, mixed Arabic-English and English) prompt-injection detector, together with a documented, labelled dataset, that reaches an F1 score of at least 0.85 on held-out Arabic and English test sets that were written separately from the training data.
3. **Keep humans in control and prove the effect (O5, O6).** By milestone M6 (April 2027), provide a mobile approval application and a web dashboard with a tamper-evident audit log in which every blocked or approved action can be replayed. On an Arabic-extended agent benchmark (Mirsad-Bench), show that the gateway reduces attack success by at least 80% relative to an unprotected baseline while wrongly blocking no more than 5% of benign actions.

## 1.4 Scope and Constraints

@tab:scope summarises what is in and out of scope.

Table: Project scope {#tab:scope widths=1,3}
| | Items |
|---|---|
| **In scope** | Gateway core and adapters (MCP proxy, OpenAI-compatible proxy, Guard API and Python SDK); declarative policy language and engine; taint tracking; Arabic/English injection detector and its dataset; human-approval workflow with an installable mobile web application; administration dashboard; hash-chained audit log with verification and replay; a simulated enterprise workspace and demonstration agent; the Mirsad-Bench benchmark; documentation and an open-source release. |
| **Out of scope** | Protecting the LLM itself from direct jailbreaks typed by its own user; network- and host-level security; securing model training data or weights; production-grade high availability, horizontal scaling and multi-tenant isolation; integration with real customer data. |

**Technical constraints.** The project is developed by five students on personal laptops without GPUs. The demonstration agent and an LLM smoke run therefore use an open-weight model (Qwen2.5-7B) run locally through Ollama, the main benchmark uses a deterministic scripted agent, and the detector must run on a CPU within the latency budget. MCP is a young, evolving specification, so protocol handling is isolated behind an adapter layer. The demonstration environment uses simulated data only.

**Organisational constraints.** Work is limited to two academic semesters with bi-weekly supervisor meetings and a modest budget (Section 3.4.6 and Appendix A.2). Each workstream has a single owner, so cross-training and code review are needed to avoid single points of failure.

**Ethical and legal constraints.** No real personal data is used; all customers, e-mails and accounts in the demonstration workspace and benchmark are fictional and use reserved `.example` domains. Attack payloads are used only against the project's own simulated environment. The gateway must not become a privacy risk itself, so secrets are never logged and personal identifiers in the audit log are masked in line with the PDPL [@ksa2021pdpl]. AI-assisted work is disclosed (Section 3.6).

## 1.5 Stakeholders and User Personas

@tab:stakeholders lists the stakeholders, their interests and how Mirsad serves them.

Table: Stakeholders and their interests {#tab:stakeholders widths=1.4,2.4,2.2}
| Stakeholder | Interest in Mirsad | How Mirsad serves them |
|---|---|---|
| Chief Information Security Officer (CISO) / security team | Allow AI agents without creating an uncontrolled data-exfiltration channel; evidence for NCA ECC compliance | Central policies, blocked-attack statistics, tamper-evident audit evidence |
| Approvers (line managers, security analysts) | Decide quickly on risky actions without reading logs | Push alert with a plain-language Arabic/English summary and one-tap approve/deny |
| Agent developers / integrators | Secure an existing agent without rewriting it | Drop-in MCP proxy, OpenAI-compatible endpoint, Python SDK |
| Business users (employees using the agent) | Agent keeps working for legitimate tasks | Low false-positive rate; only high-risk actions are paused |
| Compliance officers / internal auditors | Reconstruct who allowed what and why | Searchable, exportable, verifiable audit log with decision replay |
| Data protection officer | PDPL compliance, no leakage of personal data | Taint rules for confidential data, masking of identifiers in logs |
| IT operations | Simple deployment and low overhead | Single-service deployment (one gateway container plus a database), health endpoint, median added latency target of at most 200 ms |
| Customers of the organisation (indirect) | Their personal data is not leaked or misused | Exfiltration and destructive actions blocked or escalated |

### 1.5.1 Stakeholder Personas

**Persona 1 – Noura Al-Qahtani, Security Operations Analyst (primary user of the approval app).** Noura, 29, works in the security operations centre of a Riyadh bank that has deployed an AI assistant for its customer-support team. She is comfortable with security tools but cannot read every log line and is often away from her desk. She needs to know immediately when the assistant attempts something risky, to understand in a few seconds *what* the agent wants to do and *why* it was paused, and to decide from her phone. She reads Arabic and English and prefers Arabic on mobile. *Goals:* fast, confident decisions; no surprises in the audit. *Frustrations:* alerts without context; false alarms. *Mirsad features:* push notification, bilingual plain-language summary, "where the data came from" section, decision in under 30 seconds.

**Persona 2 – Faisal Al-Harbi, AI Platform Engineer (agent developer).** Faisal, 33, integrates LLM agents with the bank's CRM and e-mail through MCP servers and does not want to rewrite agents each time security requirements change. *Goals:* put a control point in front of existing agents by changing a URL; express rules as configuration; test policies safely. *Frustrations:* security reviews that block releases; tools that only work with one LLM vendor. *Mirsad features:* MCP and OpenAI-compatible proxies, YAML policies with validation and monitor mode, detector playground.

**Persona 3 – Huda Al-Shehri, Compliance and Internal Audit Officer.** Huda, 41, prepares evidence for NCA ECC and PDPL audits. *Goals:* prove that controls work, reconstruct incidents, export evidence. *Frustrations:* logs that can be edited silently; decisions that cannot be explained. *Mirsad features:* HMAC hash-chained audit log, integrity verification, decision replay, CSV/JSON export.

## 1.6 Industry Relevance & IS Application

Mirsad is an information-systems solution to an organisational problem as much as a technical one. It places a *policy enforcement point* in the information flow between a new class of actor (the AI agent) and existing business systems, so that the organisation's rules, rather than the model's judgement, decide what data may leave and which actions need a human. This mirrors established IS governance practice: segregation of duties (the agent proposes, a human approves high-risk actions), least privilege (per-tool and per-parameter permissions), and accountability (a verifiable audit trail).

The work is directly relevant to Saudi organisations adopting AI under Vision 2030 [@ksa2016vision2030]. The audit and approval features support NCA ECC requirements for event logging, monitoring and access control [@nca2024ecc]; taint tracking and identifier masking support PDPL obligations [@ksa2021pdpl]; and human oversight aligns with SDAIA's AI ethics principles of accountability and human-centricity [@sdaia2025aiethics] and with the "Govern" and "Manage" functions of the NIST AI Risk Management Framework [@nist2023airmf]. Because Mirsad is model-agnostic and deployable as a single service, it suits banks, government service portals, telecom and e-commerce customer support, sectors in which agents would handle Arabic-language customer data.

## 1.7 Project Timeline (Gantt Chart)

The project follows the two-semester plan in the approved proposal: Senior Project I (Fall 2026) covers investigation, requirements, design and a working prototype; Senior Project II (Spring 2027) covers the full implementation, testing, evaluation and final delivery. @tab:phases lists the phases with their durations and responsible members, @tab:milestones lists the milestones and the objectives they evidence, and @fig:gantt shows the schedule, task owners and milestones. Members are abbreviated as BS (Bader Alshuraie), AO (Abdullah Naif Abdullah Al-Orabi), BY (Bader Abdullah Abbod Alyamini), MA (Mohammed Yasser Alanssari) and AB (Abdulmalik bin Saedan); ALL means the whole team. The weekly breakdown against the IS499 deliverables D1–D6 is given in Section 3.4.

Table: Project phases, durations and responsible members (from the D2 work breakdown) {#tab:phases widths=2,1.6,0.8,1.6}
| Phase | Planned dates | Duration | Responsible |
|---|---|---|---|
| Project management (whole project) | 1 Sep 2026 – 20 May 2027 | 37 weeks | AB |
| 1 Investigation and requirements | 1 Sep – 25 Oct 2026 | 8 weeks | ALL (threat model BY, AB; benchmark and dataset design AB, AO) |
| 2 Design | 18 Oct – 15 Nov 2026 | 4 weeks | BS, BY, MA |
| 3 Prototype (Senior Project I) | 15 Nov – 24 Dec 2026 | 6 weeks | BS, BY, AO, ALL |
| 4 Implementation I | 10 Jan – 20 Feb 2027 | 6 weeks | AO, BY, BS |
| 5 Implementation II | 1 Feb – 20 Mar 2027 | 7 weeks | MA, AB, BS, BY |
| 6 Testing and evaluation | 10 Mar – 20 Apr 2027 | 6 weeks | ALL (benchmark AB, detector evaluation AO, penetration test AB, BY, MA) |
| 7 Finalization | 10 Apr – 20 May 2027 | 6 weeks | MA, BS, ALL |

The dates are the baseline of the project plan. Actual progress ran ahead of it: on the evidence date of this report ({{reports/results_summary.json#generated_at}}), before the M1 baseline date, a working and tested prototype of the components planned for phases 3 to 5 already existed (Chapter 4), while the results that depend on team-authored attack data, which M4 and M6 require, were still open. D2 (Section 3.5) records progress against the baseline.

Table: Project milestones {#tab:milestones widths=0.6,3.2,1.2,1}
| ID | Milestone | Target date | Objectives |
|---|---|---|---|
| M1 | Proposal approved; threat model and SRS agreed | 20 Oct 2026 | 1, 2, 3 (scoping) |
| M2 | Architecture and policy language approved | 15 Nov 2026 | 1 |
| M3 | Prototype intercepts MCP traffic with basic policies (Senior Project I demo) | 20 Dec 2026 | 1 |
| M4 | Taint tracking and Arabic/English detector integrated | 20 Feb 2027 | 1, 2 |
| M5 | Approval app, dashboard and audit log complete | 20 Mar 2027 | 1, 3 |
| M6 | Benchmark results and security testing complete | 20 Apr 2027 | 2, 3 |
| M7 | Final report, poster, presentation and open-source release | 20 May 2027 | all |

![Project schedule with task owners (abbreviations as in the text) and milestones M1–M7](docs/figures/gantt.png){#fig:gantt width=6.2}
