# 1 Introduction

## 1.1 Purpose of this document

This document is deliverable D2 (Work Plan and Budget) of the IS499 Senior Project **Mirsad** (مرصاد), a runtime security gateway that sits between large language model (LLM) agents and the tools they call. Mirsad checks every tool call against a declarative YAML policy, tracks where data came from (taint tracking), scans tool results for injected instructions in Arabic and English, asks a human to approve high-risk actions through an installable mobile web app, and records every decision in a tamper-evident audit log.

D2 explains how the five-member team divides, schedules, resources and funds this work across Senior Project I (Fall 2026) and Senior Project II (Spring 2027). It revises the plan and budget submitted with the Senior Project Agreement and Proposal (SPAP) and records the status of each project risk on 11 October 2026.

## 1.2 Sources and how the plan is kept current

The plan is kept as data rather than prose. Phases, work packages, owners, dates and milestones are defined once in `docs/pm/plan.yaml`. The Gantt chart is generated from that file by `scripts/make_pm_figures.py`, and the work breakdown, milestone and weekly tables in this document use the same data. Every price in Section 5 was read from the vendor's own page on 11 October 2026 and is cited. Every measured value in the risk register is read from `reports/results_summary.json` when the document is built, so the text cannot drift from the evidence.

The team works in two-week Scrum sprints [@schwaber2020scrum], with a product backlog, a sprint review in the bi-weekly supervisor meeting and a retrospective at the end of each sprint. Security work (threat modelling, code review, static analysis, dependency scanning and security tests) is part of every sprint. The public interfaces between workstreams are fixed in an engineering contract (`docs/dev/BUILD_SPEC.md`) so that the five workstreams can proceed in parallel.

Table: Planning baseline {#tab:d2-baseline widths=1.5,4.5}
| Item | Value |
|---|---|
| Duration | 1 September 2026 to 20 May 2027, with a winter break from 25 December 2026 to 9 January 2027 |
| Structure | 7 phases, 26 work packages, 17 sprints, 7 milestones (M1–M7) |
| Team | 5 students (2 Software Engineering, 3 Information Systems – Cybersecurity); supervisor Dr. Omaia Al-Omari |
| Budget | 1,185 SAR revised (SPAP: 1,660 SAR), with a documented zero-cost fallback |
| Plan sources | `docs/pm/plan.yaml` (schedule and owners), `docs/research/budget-evidence.md` (prices) |

## 1.3 Structure of the document

Section 2 breaks the work into work packages with owners and outputs. Section 3 gives the schedule, milestones, sprint plan and critical path. Section 4 maps the 15-week IS499 calendar and deliverables D1–D6 to the team plan. Section 5 presents the original and revised budgets with their price evidence and a zero-cost fallback. Section 6 is the risk register, and Section 7 lists the people, hardware, software and accounts the project needs.

# 2 Work Breakdown Structure

## 2.1 Work packages

The project is decomposed into seven phases (level 1) and 26 work packages (level 2). @tab:d2-wbs lists each work package with its owner, planned dates and main output. Owners are abbreviated as BS (Bader Alshuraie), AO (Abdullah Naif Abdullah Al-Orabi), BY (Bader Abdullah Abbod Alyamini), MA (Mohammed Yasser Alanssari) and AB (Abdulmalik bin Saedan); ALL means the whole team. Project management (WBS 0) is a level-of-effort activity that runs for the whole project and is therefore not drawn in the Gantt chart.

A work package is complete when its output has been reviewed by a second team member, its automated tests pass, and its documentation under `docs/` is up to date.

Table: Work breakdown structure {#tab:d2-wbs widths=0.55,2.1,0.75,1.25,2.35}
| WBS | Work package | Owner | Planned dates | Main output |
|---|---|---|---|---|
| **0** | **Project management** | AB | 1 Sep 2026 – 20 May 2027 | Sprint plans, risk register, budget log, progress reporting to the supervisor |
| **1** | **Investigation and requirements** | | 1 Sep – 25 Oct 2026 | |
| T1.1 | Literature review and related products | ALL | 1 Sep – 30 Sep 2026 | Literature review; research notes in `docs/research/` |
| T1.2 | Threat model (STRIDE) and attack taxonomy | BY, AB | 14 Sep – 8 Oct 2026 | Threat model and data-flow diagrams; abstract attack categories |
| T1.3 | Requirements analysis and SRS (D3) | ALL | 21 Sep – 20 Oct 2026 | D3 SRS; requirement baseline at M1 |
| T1.4 | Benchmark and dataset design | AB, AO | 1 Oct – 25 Oct 2026 | Mirsad-Bench scenario schema; dataset labelling guidelines |
| **2** | **Design** | | 18 Oct – 15 Nov 2026 | |
| T2.1 | Architecture and high/low-level design (D4) | BS | 18 Oct – 12 Nov 2026 | D4; engineering contract |
| T2.2 | Policy language specification | BS | 20 Oct – 10 Nov 2026 | YAML policy schema version 1 (`docs/policy-language.md`) |
| T2.3 | Database and audit-chain design | BY | 25 Oct – 12 Nov 2026 | Entity-relationship model; HMAC hash-chain design |
| T2.4 | UI wireframes (dashboard and approver app) | MA | 25 Oct – 15 Nov 2026 | Wireframes for the dashboard and the approver PWA |
| **3** | **Prototype (Senior Project I)** | | 15 Nov – 24 Dec 2026 | |
| T3.1 | Gateway, MCP proxy and basic policies | BS | 15 Nov – 15 Dec 2026 | Gateway pipeline, MCP proxy, policy engine |
| T3.2 | Audit log and storage | BY | 15 Nov – 10 Dec 2026 | Hash-chained audit log; database layer |
| T3.3 | Dataset authoring (Arabic/English) starts | AO, ALL | 15 Nov – 20 Dec 2026 | First labelled batches, benign and attack-labelled |
| T3.4 | Senior Project I report and prototype demo | ALL | 10 Dec – 24 Dec 2026 | Midterm report; prototype demonstration (M3) |
| **4** | **Implementation I** | | 10 Jan – 20 Feb 2027 | |
| T4.1 | Injection detector (rules and model) and training | AO | 10 Jan – 20 Feb 2027 | Detector package; trained model; metrics report |
| T4.2 | Taint tracking engine | BY | 10 Jan – 15 Feb 2027 | Taint tracker and its four flow rules |
| T4.3 | OpenAI-compatible proxy and SDK | BS | 20 Jan – 20 Feb 2027 | `/v1/chat/completions` proxy; Python SDK |
| **5** | **Implementation II** | | 1 Feb – 20 Mar 2027 | |
| T5.1 | Approver PWA and notifications | MA | 1 Feb – 15 Mar 2027 | Installable approver app; Web Push |
| T5.2 | Administration dashboard (English/Arabic) | MA | 1 Feb – 20 Mar 2027 | Dashboard pages with right-to-left Arabic layout |
| T5.3 | Demo workspace and LLM demo agent | AB | 10 Feb – 15 Mar 2027 | Simulated workspace of a fictional company; demonstration agent |
| T5.4 | Approval workflow and administration API | BS, BY | 15 Feb – 20 Mar 2027 | Approval service; REST administration API |
| **6** | **Testing and evaluation** | | 10 Mar – 20 Apr 2027 | |
| T6.1 | Unit, integration and UI tests (D5) | ALL | 10 Mar – 10 Apr 2027 | Automated test suites; D5 |
| T6.2 | Mirsad-Bench runs (scripted and LLM agents) | AB | 15 Mar – 15 Apr 2027 | Benchmark reports |
| T6.3 | Detector evaluation and error analysis | AO | 15 Mar – 10 Apr 2027 | Held-out results; error analysis |
| T6.4 | Penetration test of the gateway | AB, BY, MA | 25 Mar – 20 Apr 2027 | Security test report |
| **7** | **Finalization** | | 10 Apr – 20 May 2027 | |
| T7.1 | User guide (D6) and deployment | MA, BS | 10 Apr – 30 Apr 2027 | D6; deployment files |
| T7.2 | Final report, poster and slides | ALL | 15 Apr – 10 May 2027 | Final report, poster, slides |
| T7.3 | Open-source release and final presentation | ALL | 5 May – 20 May 2027 | Public release; final presentation (M7) |

## 2.2 Responsibility summary

Each technical workstream has one accountable owner. @tab:d2-owners shows the work packages each member owns alone and those they share; the six ALL packages (T1.1, T1.3, T3.4, T6.1, T7.2 and T7.3) involve every member.

Table: Work-package ownership by member {#tab:d2-owners widths=1.6,1.6,1.4,1.4}
| Member | Workstream | Sole owner | Shared |
|---|---|---|---|
| Bader Alshuraie (BS) | Gateway core, adapters, policy engine | T2.1, T2.2, T3.1, T4.3 | T5.4, T7.1 |
| Abdullah Naif Abdullah Al-Orabi (AO) | Detector and dataset | T4.1, T6.3 | T1.4, T3.3 (lead) |
| Bader Abdullah Abbod Alyamini (BY) | Taint tracking and audit log | T2.3, T3.2, T4.2 | T1.2, T5.4, T6.4 |
| Mohammed Yasser Alanssari (MA) | Dashboard and approver PWA | T2.4, T5.1, T5.2 | T6.4, T7.1 |
| Abdulmalik bin Saedan (AB) | Project management, demo workspace and agent, benchmark, security testing | WBS 0, T5.3, T6.2 | T1.2, T1.4, T6.4 |

# 3 Schedule

## 3.1 Gantt chart

@fig:d2-gantt shows the schedule generated from `docs/pm/plan.yaml`. Phases overlap on purpose: design starts while requirements are being finalised, and the two implementation phases run in parallel because they belong to different owners. The winter break (25 December 2026 to 9 January 2027) is shaded and contains no planned work.

![Mirsad schedule generated from docs/pm/plan.yaml: 26 work packages in seven phases with their owners, and milestones M1–M7 shown as red diamonds](docs/figures/gantt.png){#fig:d2-gantt width=6.0}

## 3.2 Milestones

Each milestone closes a phase and is tied to proposal objectives O1–O6. @tab:d2-milestones also states the evidence the team will present to the supervisor to show that the milestone has been reached.

Table: Milestones and completion evidence {#tab:d2-milestones widths=0.5,2.0,1.0,0.8,2.2}
| ID | Milestone | Target date | Objectives | Completion evidence |
|---|---|---|---|---|
| M1 | Proposal approved; threat model and SRS agreed | 20 Oct 2026 | O1–O6 scoped | Approved SPAP; D3 accepted as the requirement baseline |
| M2 | Architecture and policy language approved | 15 Nov 2026 | O1, O2 | D4 reviewed; policy schema version 1 frozen |
| M3 | Prototype intercepts MCP traffic with policies | 20 Dec 2026 | O1, O2 | Live demonstration of MCP calls allowed, denied and audited according to a policy |
| M4 | Taint tracking and detector integrated | 20 Feb 2027 | O3, O4 | Taint rules and detector active in the gateway; detector metrics on held-out Arabic and English test sets |
| M5 | Approval app, dashboard and audit complete | 20 Mar 2027 | O5 | Approval round trip from a phone; audit verification and decision replay in the dashboard |
| M6 | Benchmark and security testing complete | 20 Apr 2027 | O6 | Mirsad-Bench reports, including attack success rate; security test report |
| M7 | Final submission and presentation | 20 May 2027 | All | Final report, poster, slides and public release |

## 3.3 Sprint plan

The 17 sprints in @tab:d2-sprints turn the work packages into two-week goals. Sprints S1–S8 belong to Senior Project I and S9–S17 to Senior Project II; the last sprint is extended to the final presentation date.

Table: Sprint plan summary {#tab:d2-sprints widths=0.6,1.5,3.3,0.6}
| Sprint | Dates | Sprint goal | Milestone |
|---|---|---|---|
| S1 | 1–14 Sep 2026 | Literature review, product analysis, team setup, repository and CI skeleton | |
| S2 | 15–28 Sep 2026 | Threat model, attack taxonomy, stakeholder personas | |
| S3 | 29 Sep–12 Oct 2026 | SRS: functional and non-functional requirements, use cases | |
| S4 | 13–26 Oct 2026 | Benchmark and dataset design; requirement baseline agreed | M1 |
| S5 | 27 Oct–9 Nov 2026 | Architecture, engineering contract, policy language, database design | |
| S6 | 10–23 Nov 2026 | UI wireframes; gateway core and MCP proxy | M2 |
| S7 | 24 Nov–7 Dec 2026 | Policy engine, rate limiter, audit log and storage | |
| S8 | 8–21 Dec 2026 | Prototype demonstration and Senior Project I report | M3 |
| S9 | 10–23 Jan 2027 | Taint tracking; detector normalisation and rules | |
| S10 | 24 Jan–6 Feb 2027 | Detector model and dataset pipeline; OpenAI-compatible proxy and SDK | |
| S11 | 7–20 Feb 2027 | Detector training and evaluation; integration | M4 |
| S12 | 21 Feb–6 Mar 2027 | Approval workflow, approver PWA, notifications | |
| S13 | 7–20 Mar 2027 | Dashboard, demo workspace and demo agent | M5 |
| S14 | 21 Mar–3 Apr 2027 | Test specification and automated tests (D5); benchmark runs | |
| S15 | 4–17 Apr 2027 | Security testing; latency and evaluation report | |
| S16 | 18 Apr–1 May 2027 | User guide (D6), deployment, documentation | M6 |
| S17 | 2–20 May 2027 | Final report, poster, presentation and open-source release | M7 |

## 3.4 Dependencies and critical path

Most work packages depend only on the engineering contract, so they can run in parallel. The chain that sets the end date runs through the data:

1. T1.3 (requirements) and T1.4 (dataset design) fix what the detector must recognise and how test data is kept apart from training data.
2. T3.3 (dataset authoring) must deliver attack-labelled batches written by the team before T4.1 can train a model.
3. T4.1 (detector) and T5.3 (demo workspace) must both be ready before T6.2 (benchmark runs) and T6.3 (detector evaluation) can produce the results that M6 requires.
4. T6.2 and T6.3 feed T7.2 (final report).

Any delay in the team-authored data moves M4 and M6. Section 6 records this as risk R2, which has already occurred.

## 3.5 Progress against the baseline

The baseline dates above are kept for reporting to the supervisor. At the time of the recorded evidence run ({{reports/results_summary.json#generated_at}}; Appendix B.1 of the final report), the repository already contains working implementations of the components planned for phases 3 to 5: the gateway and its adapters, the policy engine, taint tracking, the detector's normalisation, rules and training pipeline, the audit log, the approval service, the dashboard, the approver PWA, the demo workspace and Mirsad-Bench. The automated suites hold {{reports/results_summary.json#python_tests.total|,}} Python tests ({{reports/results_summary.json#python_tests.failed}} failing) and {{reports/results_summary.json#web_tests.total|,}} web tests ({{reports/results_summary.json#web_tests.failed}} failing), with {{reports/results_summary.json#coverage.percent|.1f}}% statement coverage of the core package.

The work that remains on the critical path is the team-authored labelled data (T3.3), training and evaluating the detector on it (T4.1, T6.3), running the benchmark's attack episodes on the team's attack files (T6.2), the penetration test (T6.4), verifying the Docker deployment (T7.1) and the documentation deliverables. Implemented work packages move to review and hardening in their scheduled sprints.

# 4 Weekly Task Breakdown

## 4.1 Mapping the IS499 calendar to the team plan

The IS499 syllabus places deliverables D1–D6 on a single 15-week calendar, while the Mirsad plan spreads the same work over two semesters. @tab:d2-weekly links each syllabus week to the work packages and sprints that produce its deliverable, so the supervisor can check any week of the syllabus against the team plan. Submission dates for each syllabus week are set by the course coordinator; the table fixes only which work is due at that point.

Table: IS499 weekly breakdown mapped to the team plan {#tab:d2-weekly widths=0.5,1.5,1.2,0.8,0.8,1.9}
| Week | IS499 activity or deliverable | Work packages | Sprints | Lead | Output |
|---|---|---|---|---|---|
| 1 | D1 Project proposal | T1.1, WBS 0 | S1 | ALL | SPAP form; repository and CI skeleton |
| 2 | D2 Work plan and budget (drafting) | T1.1, WBS 0 | S1–S2 | AB | Work breakdown, Gantt chart, price evidence |
| 3 | D2 submission | T1.2, WBS 0 | S2 | AB | D2 (this document) with risk register |
| 4 | D3 SRS (elicitation and analysis) | T1.2, T1.3 | S3 | ALL | Threat model; requirement and use-case drafts |
| 5 | D3 submission | T1.3, T1.4 | S3–S4 | ALL | D3 SRS; requirement baseline (M1) |
| 6 | D4 design (architecture) | T2.1, T2.2 | S5 | BS | Architecture, engineering contract, policy schema |
| 7 | D4 submission | T2.3, T2.4 | S5–S6 | BY, MA | D4 with database, audit-chain and UI design (M2) |
| 8 | Midterm report (D1–D4) | T3.4 | S8 | ALL | Senior Project I report and prototype demonstration (M3) |
| 9 | Implementation iteration 1 | T3.1, T3.2, T4.2 | S7, S9 | BS, BY | Policy engine, audit log, taint tracker |
| 10 | Implementation iteration 1 review | T3.3, T4.1, T4.3 | S10–S11 | AO, BS | Detector model and metrics; OpenAI-compatible proxy and SDK (M4) |
| 11 | Implementation iteration 2 | T5.1, T5.4 | S12 | MA, BS, BY | Approval workflow, approver PWA, notifications |
| 12 | Implementation iteration 2 review | T5.2, T5.3 | S13 | MA, AB | Dashboard; demo workspace and agent (M5) |
| 13 | D5 test cases and results; D6 user guide | T6.1–T6.4, T7.1 | S14–S16 | ALL | D5, D6, benchmark and security reports (M6) |
| 14 | Final report | T7.2 | S17 | ALL | Final report and poster |
| 15 | Final presentation | T7.3 | S17 | ALL | Presentation and open-source release (M7) |

## 4.2 Weekly routine

Every sprint starts with planning from the product backlog and ends with a review in the supervisor meeting. The project manager updates the risk register and the budget log at the end of each sprint and reports any milestone at risk at the next supervisor meeting. Before each deliverable is submitted, the evidence script (`scripts/run_evidence.sh`) is run again, so the numbers quoted in a deliverable come from the code as submitted.

# 5 Budget

All amounts are in Saudi riyals (SAR). US-dollar prices are converted at the official peg of 3.75 SAR per USD [@sama2020-peg]. Vendor prices exclude VAT and card or foreign-exchange fees unless the page says otherwise; the contingency line covers them.

## 5.1 Original SPAP budget

Table: Original budget in the SPAP {#tab:d2-budget-spap widths=3,1}
| Line | Amount (SAR) |
|---|---:|
| LLM API usage | 750 |
| Cloud virtual machine | 600 |
| Google Play developer registration | 100 |
| Domain name and TLS certificate | 60 |
| Contingency | 150 |
| **Total** | **1,660** |

The SPAP gave these figures without price sources or a token model for the LLM line.

## 5.2 Decisions that changed the budget

Two design decisions made after the proposal change what the project must buy:

1. **Local models for development and most of the evaluation.** Ollama is an open-source runtime that serves open-weight models on the team's own machines with no usage fee [@ollama-repo], and it exposes an OpenAI-compatible API with tool calling [@ollama-openai-compat]. Mirsad's OpenAI-style adapter therefore needs no second code path, and paid API calls are kept for one confirmatory run per cloud provider.
2. **A Progressive Web App (PWA) instead of store-distributed native approval apps.** Web Push works for web apps on Android and, since iOS and iPadOS 16.4, for web apps added to the Home Screen, without a developer-program membership [@eidson2023-webpush]. This removes the Google Play line and avoids an Apple fee that the SPAP never counted.

## 5.3 Revised budget

Table: Original and revised budget (SAR) {#tab:d2-budget widths=2.2,0.9,0.9,2.0}
| Line | SPAP | Revised | Change |
|---|---:|---:|---|
| LLM API usage | 750 | 450 | Local models for development; one confirmatory run per provider |
| Cloud VM (2 vCPU, 4 GB, 6 months) | 600 | 540 | Priced from plans that can be ordered today |
| Google Play registration | 100 | 0 | PWA instead of store apps |
| Domain and TLS | 60 | 45 | .com domain; free certificate |
| Contingency | 150 | 150 | About 14.5% of the 1,035 SAR subtotal |
| **Total** | **1,660** | **1,185** | **Saving 475 SAR (28.6%)** |

### 5.3.1 LLM API usage: 450 SAR

The confirmatory run uses one mid-tier model from each of two providers: Claude Sonnet 5.5 at $2 input and $10 output per million tokens [@anthropic-pricing; @anthropic-models-overview] and OpenAI `gpt-6.1-sol` at the same list prices, with function calling supported [@openai-pricing; @openai-models]. The planning assumption is about 2,000 benchmark episodes of about 6,000 tokens, or 12 million tokens per model per run. Agent episodes resend tool outputs and history on every turn, so the base case assumes 5,000 input and 1,000 output tokens per episode.

Table: LLM cost per full 2,000-episode run {#tab:d2-llm-cost widths=2.8,1.6,1.6}
| Scenario | Claude Sonnet 5.5 | gpt-6.1-sol |
|---|---:|---:|
| Base case: 10M input + 2M output tokens | $40 = 150 SAR | $40 = 150 SAR |
| Output-heavier: 8M input + 4M output tokens | $56 = 210 SAR | $56 = 210 SAR |
| Base case through a batch interface (50% discount) | $20 = 75 SAR | $20 = 75 SAR |

One base-case run on both providers costs 300 SAR and the output-heavier case 420 SAR. The 450 SAR line ($120) covers the output-heavier case, which allows for reasoning tokens billed as output [@openai-pricing] and for the higher token counts of Anthropic's newer tokenizer [@anthropic-pricing]. Multi-turn episodes need each turn's result before the next, so batch pricing is treated as a possible saving rather than assumed. Anthropic credits are prepaid, non-refundable and expire one year after purchase [@anthropic-api-credits], so credits are bought just before the run with automatic top-up switched off.

### 5.3.2 Cloud VM: 540 SAR

The VM runs only the gateway, the PWA backend and the audit database; the LLM does not run on it, so 2 vCPU and 4 GB are enough. @tab:d2-vm compares the options for six months.

Table: Cloud VM options, 2 vCPU and 4 GB for six months {#tab:d2-vm widths=2.4,1.0,1.0,1.6}
| Provider and plan | Per month | 6 months | Note |
|---|---:|---:|---|
| DigitalOcean Basic Droplet, 80 GB SSD [@digitalocean-droplets] | $24.00 | 540.00 SAR | Orderable; includes IPv4 |
| AWS Lightsail, 80 GB SSD, IPv4 [@aws-lightsail] | $24.00 | 540.00 SAR | Orderable |
| Hetzner CPX22 + IPv4 [@hetzner-price-adjustment-2026; @hetzner-ip-pricing] | $23.59 | 530.78 SAR | Orderable |
| Hetzner CX23 + IPv4 [@hetzner-price-adjustment-2026; @hetzner-ip-pricing] | $7.09 | 159.53 SAR | Listed as not available on 11 Oct 2026 [@hetzner-cloud-pages] |

Two independent providers agree on $24 per month, so the line is 6 × 90 = 540 SAR. If the cheaper Hetzner plan becomes orderable, the saving returns to contingency.

### 5.3.3 Google Play registration: 0 SAR

A Play listing would cost a one-time US$25 (93.75 SAR) [@google-play-get-started], and new personal developer accounts must first run a closed test with at least 12 testers for 14 consecutive days [@google-play-testing]. An iOS app would add 99 USD (371.25 SAR) every year [@apple-developer-enroll]. The PWA needs neither, and it can be installed from the browser on the day it is deployed.

### 5.3.4 Domain and TLS: 45 SAR

A .com name costs $11.08 (41.55 SAR) per year at Porkbun, with registration and renewal at the same price and ICANN fees included [@porkbun-domains]; the line is rounded to 45 SAR. A stable name gives the PWA a fixed HTTPS origin, which installed web apps and push subscriptions depend on. Certificates from Let's Encrypt are free [@letsencrypt-about]. HTTPS cannot be dropped because service workers run only in secure contexts [@mdn-service-worker], and the deployment must renew certificates automatically because default certificate lifetimes shorten during the project year [@mcpherrin2025-45days]. A .sa name is an option at 52.18 SAR in the first year from a licensed registrar [@saharanet-domain-pricing; @saudinic-registrars] if a team member who meets the eligibility rules registers it [@saudinic-regulations].

### 5.3.5 Contingency: 150 SAR

The contingency is kept at its SPAP value, about 14.5% of the 1,035 SAR subtotal. Prices changed sharply during 2026: Hetzner raised its CX23 price by a factor of 1.38 and its CPX22 price by 2.44 in June 2026 [@hetzner-price-adjustment-2026], and Google's paid Gemini prices are scheduled to double on 1 January 2027 [@gemini-api-pricing]. The line also covers VAT, card and exchange fees, and API reruns if a benchmark run must be repeated.

## 5.4 Zero-cost fallback

If no funding is approved, Mirsad can still be built, evaluated and demonstrated at 0 SAR, with the limits stated in @tab:d2-fallback.

Table: Zero-cost fallback plan {#tab:d2-fallback widths=1.3,2.5,2.2}
| Need | Zero-cost substitute | Limitation |
|---|---|---|
| LLM for development and the full benchmark | Ollama with open-weight models on team laptops or university lab machines [@ollama-repo; @ollama-openai-compat] | Weaker models than the cloud mid-tier; results must be labelled as local-model results |
| Cloud-model comparison | Gemini free tier on synthetic benchmark data only [@gemini-api-pricing] | Free-tier content may be used by the provider; rate limits; otherwise report that no cloud comparison was run |
| Public gateway host | Azure student credit through the GitHub Student Developer Pack [@github-student-pack; @github-education-apply]; Oracle Cloud Always Free Arm instance [@oracle-always-free]; or a lab machine behind a free Cloudflare Tunnel [@cloudflare-tunnel] | Idle Oracle instances can be reclaimed, so deployment must be scripted; a tunnel depends on the machine staying on |
| Domain | Free one-year domains in the Student Developer Pack [@github-student-pack], or a Let's Encrypt certificate for the server's IP address [@mcpherrin2026-6day-ip] | IP-address certificates last about six days and need automated renewal |
| TLS | Let's Encrypt [@letsencrypt-about] | Renewal must be automated |
| Mobile approvals | PWA with standard Web Push [@eidson2023-webpush] | iOS users must add the app to the Home Screen first |
| One-off live demo | Cloudflare Quick Tunnel [@cloudflare-quick-tunnels] | Testing only; the hostname changes on every start and Server-Sent Events are not supported, which breaks the approval stream |

If the budget is only partly funded, lines are cut in this order: the VM first (move to a student credit or the free tier), then the domain (use a pack domain), and finally the LLM line (a 1,000-episode confirmatory run, about 225 SAR).

## 5.5 Budget control

The project manager (AB) keeps a budget log of every purchase with its date, line, amount, receipt and the account it was charged to. A purchase is made only against an approved line, and no recurring subscription or automatic credit top-up is left switched on. Before any API credits are bought, the token count per episode is measured on the first 50 local episodes and the LLM line is re-costed with the formulas in @tab:d2-llm-cost.

# 6 Risk Register

## 6.1 Method

Each risk has one owner, who monitors it and carries out the mitigation. Likelihood (L) and impact (I) are rated High, Medium or Low as currently assessed. Status is one of: **Open** (may still occur), **Monitoring** (mitigations in place, measured regularly), **Occurred – mitigated** (the event happened and its effect has been contained) or **Occurred – open** (the event happened and mitigation is still in progress). The register is reviewed at the end of every sprint.

## 6.2 Proposal risks and their status

@tab:d2-risks carries forward the eight risks of the proposal (R1–R8) and records what happened during the build. Measured values are read from `reports/results_summary.json`.

Table: Risk register for the proposal risks {#tab:d2-risks widths=0.4,1.3,0.5,0.45,1.6,2.35}
| ID | Risk | Owner | L / I | Mitigation | Status and what happened |
|---|---|---|---|---|---|
| R1 | The MCP specification and its official Python SDK change quickly and break the protocol adapters. | BS | H / M | Keep all protocol handling in the adapter package; code against the engineering contract; test adapters with real MCP clients over stdio and HTTP. | **Occurred – mitigated.** The SDK moved from major version 1 to version 2 during the build, with a new client API and a renamed server class, so version 1 examples no longer work. Only the adapter package was written against version 2; the policy, taint, detector and audit packages were unaffected. {{reports/results_summary.json#python_tests.by_area.adapters}} adapter tests pass. Open action: `pyproject.toml` still accepts `mcp>=1.12`; the adapter owner's request to pin version 2 must be applied. |
| R2 | Too little labelled Arabic and English injection data to train the detector and to run attack episodes. | AO, AB | H / H | Labelling guidelines; batch-wise train/test split; held-out test batches written by a different member; public datasets with licence notes. | **Occurred – open.** The attack-labelled examples and attack templates are written by the team, not by the AI assistant used during development, and are not yet available. The repository therefore holds only benign detector data and an empty attack folder, and the detector runs on its rules-only fallback. The team supplies the data following `docs/detector.md` and `bench/scenarios/attacks/README.md`. Detector F1 (English {{reports/results_summary.json#detector.splits.test_en.f1|.2f}}, Arabic {{reports/results_summary.json#detector.splits.test_ar.f1|.2f}}) is produced by `make detector` once the data is added. Attack success rate reduction ({{reports/results_summary.json#bench.scripted_attack_oracle.configs.full.asr_reduction|.1%}}) is produced by the benchmark, which already executes attack episodes, once the attack files are added. |
| R3 | False positives and approval requests disrupt legitimate work and cause alert fatigue. | AB | M / H | Benign-only benchmark episodes for every defence configuration; monitor mode for trialling policies; plain-language approval summaries. | **Monitoring.** On {{reports/results_summary.json#bench.scripted_benign_oracle.tasks}} scripted benign tasks in English and Arabic ({{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.calls}} calls) with full protection, the automatic false-positive rate is {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.fpr|.1%}} and {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.friction|.1%}} of benign calls are escalated to a human. Utility is {{reports/results_summary.json#bench.scripted_benign_oracle.configs.full.utility|.0%}} when the approver accepts legitimate requests and {{reports/results_summary.json#bench.scripted_benign_deny.configs.full.utility|.0%}} if every escalation is denied. The friction comes from the policy layer ({{reports/results_summary.json#bench.scripted_benign_oracle.configs.policy_only.friction|.1%}} alone) and the taint layer ({{reports/results_summary.json#bench.scripted_benign_oracle.configs.taint_only.friction|.1%}} alone), not from the detector ({{reports/results_summary.json#bench.scripted_benign_oracle.configs.detector_only.friction|.1%}}); part of it falls on tasks that do not need approval, so policy tuning continues. |
| R4 | Mirsad adds more than the 200 ms median latency budget (NFR1). | BS | L / M | Asynchronous I/O; CPU-only linear detector; latency benchmark over 1,000 calls. | **Monitoring.** With the server in a separate process, the median added latency is {{reports/results_summary.json#latency.separate_process.sequential_added_p50|.1f}} ms for sequential calls and {{reports/results_summary.json#latency.separate_process.concurrent_added_p50|.0f}} ms (p95 {{reports/results_summary.json#latency.separate_process.concurrent_added_p95|.0f}} ms) with {{reports/results_summary.json#latency.separate_process.sessions}} concurrent sessions and {{reports/results_summary.json#latency.separate_process.concurrent_errors}} errors. Measured with the rules-only detector; to be repeated with the trained model. Tail latency under load is tracked as R10. |
| R5 | The budget is not approved, or API costs exceed it. | AB | M / M | Local models; credits bought just in time; documented zero-cost fallback (Section 5.4). | **Monitoring.** All LLM runs so far (the demonstration agent and the LLM benchmark smoke test) used Qwen2.5-7B served locally by Ollama; the scripted benchmark and the latency measurements need no LLM. Paid API calls are needed only for the confirmatory runs. The revised budget is 1,185 SAR. |
| R6 | A team member becomes unavailable and their workstream stalls (single owner per workstream). | AB | M / H | Interfaces fixed in the engineering contract; every change reviewed by a second member; a documentation page per component under `docs/`; report work shared by all. | **Open.** Mitigations are in place; the register is reviewed each sprint. |
| R7 | Vulnerabilities in the gateway or its dependencies turn the security tool into an attack surface. | BY | M / H | Threat model; dedicated security test suite; static analysis (Bandit) and dependency scanning (pip-audit, npm audit) in CI; penetration test (T6.4). | **Occurred – mitigated.** Dependency scans during the build reported vulnerable package versions, which were upgraded before the scans were repeated. Latest results: {{reports/results_summary.json#security.pip_audit_vulnerable}} vulnerable packages of {{reports/results_summary.json#security.pip_audit_packages}} audited by pip-audit, {{reports/results_summary.json#security.npm_audit_vulnerabilities}} npm audit findings, {{reports/results_summary.json#security.bandit_issues}} Bandit issues in {{reports/results_summary.json#security.bandit_loc|,}} lines, and {{reports/results_summary.json#python_tests.by_area.security}} security tests passing. Scans are repeated whenever dependencies change. |
| R8 | Development hardware or deployment tooling is not available (no GPU on team laptops; container tooling missing). | MA | M / M | CPU-only detector; 7B local model; native installation script beside Docker; PostgreSQL tested without Docker. | **Occurred – open.** Docker was not available on the machine used for the build, so the Dockerfile and `docker-compose.yml` have not been executed. The system was installed and measured natively with SQLite, and the PostgreSQL storage path is exercised by integration tests against an embedded PostgreSQL server. NFR5 (deployment with one `docker compose up`) stays unverified until the stack runs on a machine with Docker; the CI workflow contains a Docker build job for this check. |

## 6.3 Risks added during the build

Three risks were identified during the build and added to the register.

Table: Risks added during the build {#tab:d2-risks-new widths=0.4,1.3,0.5,0.45,1.6,2.35}
| ID | Risk | Owner | L / I | Mitigation | Status |
|---|---|---|---|---|---|
| R9 | Components built in parallel match their interfaces but disagree in behaviour (integration defects). | BS | M / H | Engineering contract; integration and end-to-end tests; audit replay checks after every benchmark run; an integrator checklist (`docs/dev/INTEGRATOR_TODO.md`). | **Monitoring.** {{reports/results_summary.json#python_tests.by_area.integration}} integration tests pass, and {{reports/results_summary.json#bench.scripted_benign_oracle.replay_matched}} of {{reports/results_summary.json#bench.scripted_benign_oracle.replay_checked}} audited decisions in the scripted benchmark replayed to the same action. The checklist items must be closed before the final documents. |
| R10 | Tail latency grows under concurrent load in a single-worker deployment. | BS | M / M | Measure with the client in a separate process; test multiple workers and PostgreSQL before quoting a concurrency figure. | **Open.** With {{reports/results_summary.json#latency.in_process.sessions}} sessions and client and server in one Python process, p95 added latency is {{reports/results_summary.json#latency.in_process.concurrent_added_p95|.0f}} ms and p99 {{reports/results_summary.json#latency.in_process.concurrent_added_p99|.0f}} ms; with a separate server process p95 is {{reports/results_summary.json#latency.separate_process.concurrent_added_p95|.0f}} ms. |
| R11 | Code and text produced with an AI assistant contain defects or claims that the team has not checked. | AB | M / H | Disclosed use; every change passes tests, lint, static analysis and review; results quoted only from executions through `reports/results_summary.json`; every reference verified against its source. | **Monitoring.** Deliverables built from the Markdown sources take every measured value from the evidence files. Hand-written figures in the developer pages under `docs/` must be checked against them before release; for example, the latency table in `docs/benchmark.md` predates the latest run. |

# 7 Resource Plan

## 7.1 People

The team consists of five students; their workstreams and work packages are listed in @tab:d2-owners. Dr. Omaia Al-Omari supervises the project. The plan schedules a sprint review in each bi-weekly supervisor meeting and asks the supervisor to approve each milestone. The plan involves no external participants; a short questionnaire for security practitioners (Appendix F of the final report) is available if the team decides to validate requirement priorities with practitioners.

## 7.2 Hardware

Table: Hardware resources {#tab:d2-hardware widths=1.6,2.6,1.0}
| Resource | Use | Cost |
|---|---|---|
| Team members' personal laptops (no GPU) | Development, tests, local Ollama model (Qwen2.5-7B), benchmark runs | Owned |
| University lab machines | Fallback for long benchmark runs and for a tunnel-hosted demo | Free |
| At least one Android phone and one iPhone (iOS 16.4 or later) from team members | Installing the approver PWA and testing Web Push on both platforms | No purchase planned |
| Cloud VM, 2 vCPU and 4 GB, for six months | Public demonstration gateway with HTTPS | 540 SAR (Section 5.3.2) |

## 7.3 Software

Apart from Microsoft Word, which is used for the IS499 document template, the tools in @tab:d2-software are open-source software or free services, and none is charged to the project budget. The adapters require version 2 of the official MCP Python SDK.

Table: Software resources {#tab:d2-software widths=1.4,3.0,1.6}
| Area | Tools | Used in |
|---|---|---|
| Gateway and API | Python 3.12, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0, MCP Python SDK v2, httpx | T3.1, T4.3, T5.4 |
| Detector | scikit-learn, NumPy, YAML rule files | T4.1, T6.3 |
| Storage | SQLite (development), PostgreSQL 16 (deployment) | T2.3, T3.2 |
| Web | React 18, TypeScript, Vite, Recharts, Node.js | T5.1, T5.2 |
| LLM runtime | Ollama with Qwen2.5-7B | T5.3, T6.2 |
| Quality and security | pytest, Vitest, Ruff, Bandit, pip-audit, npm audit | T6.1, T6.4 |
| Deployment | Docker and Docker Compose, GitHub Actions | T7.1 |
| Documentation | Markdown, Mermaid, Matplotlib, python-docx, Microsoft Word | All deliverables |

The team also uses an AI coding and writing assistant (Anthropic's Claude), whose use is disclosed in the final report and controlled as described under R11.

## 7.4 Accounts and external services

Table: Accounts and external services {#tab:d2-accounts widths=1.6,2.4,1.0,1.0}
| Account or service | Purpose | Holder | Cost |
|---|---|---|---|
| GitHub repository and GitHub Actions | Version control, reviews, CI | Team | Free |
| GitHub Student Developer Pack (each member) | Student cloud credit, free domain, developer tools [@github-student-pack; @github-education-apply] | Each member | Free |
| Anthropic and OpenAI API accounts | Confirmatory benchmark runs | Project manager | Within the 450 SAR LLM line |
| VM provider (DigitalOcean or AWS Lightsail) | Demonstration gateway | Project manager | Within the 540 SAR VM line |
| Domain registrar | Project domain for a stable HTTPS origin | Project manager | Within the 45 SAR line |
| Let's Encrypt | TLS certificates | Deployment owner | Free |
| Web Push (VAPID key pair) | Approval notifications through browser push services | Generated on the server | Free |

Secrets for these accounts are never committed to the repository. The required settings are listed in `.env.example` and are supplied through environment variables at deployment time.
