# Appendix F – Stakeholder Questionnaire

This questionnaire validates Mirsad's requirement priorities with security and IT practitioners in the target sectors (banking, government services, telecom, e-commerce). It takes about ten minutes, collects no personal data beyond role and sector, and participation is voluntary and anonymous. It is available in English and Arabic; responses are to be summarised in aggregate only.

**Consent.** "This survey is part of a Prince Sultan University senior project. Your answers are anonymous and used only in aggregate for academic purposes. You may stop at any time. By continuing you agree to take part."

Table: Section A – Respondent profile {#tab:qA widths=0.5,3.5,2}
| # | Question | Answer format |
|---|---|---|
| A1 | Which best describes your role? | SOC / security analyst · security manager / CISO · IT / platform engineer · developer · compliance / audit · other |
| A2 | Sector of your organisation | Banking / finance · government · telecom · healthcare · e-commerce / retail · education · other |
| A3 | Does your organisation use, pilot or plan to use AI agents that can call tools (e-mail, CRM, APIs)? | In production · piloting · planned within 12 months · no plans |
| A4 | In which languages do your users and customers communicate with these systems? | Arabic · English · both · other |

Table: Section B – Importance of capabilities (1 = not important, 5 = critical) {#tab:qB widths=0.5,4.5,1}
| # | Capability | 1–5 |
|---|---|---|
| B1 | Blocking an AI agent from sending company data to external addresses | |
| B2 | Rules per tool and per parameter (e.g. "never export more than 50 records") | |
| B3 | Detecting hidden instructions in e-mails, web pages and documents in **Arabic** | |
| B4 | Detecting hidden instructions in **English** | |
| B5 | Asking a human to approve high-risk actions (payments, deletions, bulk exports) | |
| B6 | Approving from a mobile phone with a short explanation | |
| B7 | A tamper-evident audit log usable as compliance evidence (NCA ECC, PDPL) | |
| B8 | Working with any LLM provider (no vendor lock-in) | |
| B9 | Low added delay (below 0.2 s per tool call) | |
| B10 | Deployment on-premises / in a Saudi data centre | |

Table: Section C – Operational preferences {#tab:qC widths=0.5,3.5,2}
| # | Question | Answer format |
|---|---|---|
| C1 | Within how many seconds should an approver normally decide on a paused action? | < 30 s · 30–60 s · 1–5 min · > 5 min |
| C2 | If nobody responds to an approval request, what should happen? | Deny (fail-safe) · allow · escalate to another approver |
| C3 | What false-alarm rate (benign actions paused) would be acceptable? | < 1% · 1–5% · 5–10% · > 10% |
| C4 | Preferred language for alerts | Arabic · English · both |
| C5 | Which actions should always need human approval in your context? | Free text |
| C6 | What would stop your organisation from adopting a gateway like Mirsad? | Free text |

Table: Section D – After a demonstration (optional, 1 = strongly disagree, 5 = strongly agree) {#tab:qD widths=0.5,4.5,1}
| # | Statement | 1–5 |
|---|---|---|
| D1 | I understood why the action was paused from the approval summary alone. | |
| D2 | I could decide on the request in under 30 seconds. | |
| D3 | The dashboard makes it clear which attacks were blocked and why. | |
| D4 | I would trust the audit log as evidence in an audit. | |
| D5 | The Arabic interface is clear and natural. | |

**Analysis plan.** Section B priorities are reported as medians and the share of respondents rating 4–5; items with a median below 3 are candidates to lower in priority, and free-text answers in C5–C6 are coded thematically into new backlog items. Section D gives a small usability check of NFR4 to complement the Keystroke-Level Model estimate in Chapter 4.
