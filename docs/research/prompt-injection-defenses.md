# Literature Review Track: Defenses Against Prompt Injection

**Project:** Mirsad (مرصاد), a runtime security firewall for LLM agents and their tools
**Course:** IS499 Senior Project, Prince Sultan University, 2026-2027
**Track:** Defenses against (indirect) prompt injection: detectors, prompt-level marking, training-time defenses, runtime guardrails, and system-level architectures
**Prepared:** 11 October 2026
**Sources:** 30 references (peer-reviewed papers, arXiv preprints, official vendor documentation, and model cards), numbered in IEEE style in the order of the annotated entries.

> **Verification note.** Every reference was checked on 11 Oct 2026 against a reachable primary record: the arXiv abstract page, the ACL Anthology (BibTeX export), USENIX presentation pages, PMLR, CEUR-WS, Crossref DOI metadata, the Hugging Face model card and API, the GitHub repository, or the vendor's own documentation site. Details that could not be confirmed (for example, page numbers for preprints, or a release date that a model card does not state) are left out instead of guessed. Numbers are the values reported by the authors or vendors and have not been reproduced by the Mirsad team. Vendor claims (Lakera, Microsoft) are marked as such. An independent fact-check pass on the same date re-verified every entry and corrected a few details; see the Verification log at the end.

---

## 1. Introduction

Mirsad sits between an LLM agent and its tools, so the main design question for the project is which defenses belong in that position and which belong elsewhere. Published defenses against prompt injection work at four different layers. At the **model** layer, the LLM is trained to give less weight to instructions that arrive in data: Instruction Hierarchy, StruQ, SecAlign, and Meta-SecAlign. At the **prompt** layer, untrusted text is marked or transformed before the model sees it, as in Spotlighting. At the **runtime** layer, a classifier or monitor screens inputs, outputs, or tool calls: Prompt Guard 2, ProtectAI's DeBERTa model, PIGuard, Lakera Guard, Azure Prompt Shields, Rebuff, NeMo Guardrails, LlamaFirewall, MELON, AgentSpec, and Progent. At the **architecture** layer, the agent is restructured so that untrusted data cannot change control flow or reach sensitive sinks: IsolateGPT, f-secure, CaMeL, FIDES, and the design patterns of Beurer-Kellner et al. For each source this review records (a) the layer it works at, (b) what the agent developer has to supply or change to adopt it, and (c) whether it documents multilingual or Arabic support. The review then turns to the 2024-2026 evaluation literature: adaptive gradient, search, and RL attacks, character-level evasion, and large human red-teaming competitions have bypassed nearly every detector and trained defense they were tested against. The synthesis argues that a detector, Arabic-capable or not, cannot be Mirsad's security boundary. That boundary has to be deterministic, policy-based enforcement at the tool-call interface, with the detector, human approval, and the audit log as supporting layers.

---

## 2. Overview Table

| # | Defense | Layer | What the agent developer must supply or change | Multilingual / Arabic (as documented) |
|---|---|---|---|---|
| [1] | Llama Prompt Guard 2 (Meta) | Runtime classifier | Run an 86M/22M model on each untrusted input, split into 512-token chunks; pick a threshold; optional fine-tuning | 86M: en, fr, de, hi, it, pt, es, th. **No Arabic** |
| [2] | ProtectAI `deberta-v3-base-prompt-injection-v2` | Runtime classifier | Run the model on inputs (card examples truncate at 512 tokens); project now archived | **English only** |
| [3] | PIGuard (ACL 2025) | Runtime classifier | Run the model; tune the threshold for over-defense | Not documented (HF card lists en) |
| [4]-[5] | Lakera Guard / Check Point AI Guardrails | Runtime screening service (SaaS; self-hosting requires an enterprise license) | Call `POST /v2/guard` at every turn and tool call with role-tagged messages; configure a policy and sensitivity level | Vendor claims 100+ languages, including "Arabic and other Semitic languages" |
| [6]-[7] | Azure AI Prompt Shields | Runtime SaaS screening + optional Spotlighting | Send the user prompt and up to 5 documents (10K characters) per call, or enable a Foundry guardrail at the tool-response point | **Tested in English only**; "may work" in other languages |
| [8] | Rebuff (Protect AI) | Runtime multi-layer detector | Heuristics + LLM judge + vector DB + canary tokens; needs an external LLM and a vector store. Archived | Not documented |
| [9] | Ara-Prompt-Guard_V0 (NAMAA) | Runtime classifier | Run the 3-class model on Arabic inputs | **Arabic (MSA) only** |
| [10] | Spotlighting (Microsoft) | Prompt | Rewrite the system prompt; delimit, datamark, or encode every untrusted document | Not evaluated |
| [11] | Instruction Hierarchy (OpenAI) | Model (training) | Nothing directly; depends on the model provider | Not documented |
| [12] | StruQ | Model (training) + front-end | Fine-tune an open model; route data through a separate delimited channel | Not documented |
| [13] | SecAlign | Model (preference optimization) | DPO/LoRA fine-tuning of open weights; keep the instruction/data template | Not documented |
| [14] | Meta-SecAlign | Model (training) | Use or train a secured open-weight model; place untrusted data in the data role | Not documented |
| [15] | NeMo Guardrails (NVIDIA) | Runtime framework | Write Colang flows and Python actions; configure input/output rails | Not discussed in the paper |
| [16] | LlamaFirewall (Meta) | Runtime framework | Wire scanners (PromptGuard 2, AlignmentCheck, CodeShield, regex/LLM custom scanners) to message roles; choose a guardrail LLM | PG2-86M multilingual (8 languages, no Arabic); AlignmentCheck not evaluated across languages |
| [17] | MELON (ICML 2025) | Runtime monitor (behavioral) | Re-run each agent step with a masked user prompt and compare tool calls | Language-agnostic by design; not evaluated |
| [18] | AgentSpec (ICSE 2026) | Runtime policy enforcement | Write DSL rules (trigger, check, enforce) and predicates; hook into the agent loop (LangChain is the main implementation) | Not applicable (rule-based) |
| [19] | Progent | Runtime policy enforcement | JSON-Schema privilege policies (manual or LLM-generated); library mode or MCP/LLM proxy mode; an approver for policy expansions | Not applicable (rule-based) |
| [20] | IsolateGPT (NDSS 2025) | Architecture (isolation) | Restructure into a hub with isolated per-app "spokes"; declare inter-app interfaces | Not documented |
| [21] | f-secure | Architecture (IFC) | Planner emits structured plans; security monitor plus rule-based executor | Not documented |
| [22] | CaMeL (Google/ETH) | Architecture (capabilities + IFC) | Custom interpreter; P-LLM/Q-LLM split; Python security policies; capability-tagging tools | Not documented |
| [23] | FIDES (Microsoft) | Architecture (IFC planner) | Label tools and data (integrity/confidentiality); classify tools as consequential or egress; assign policies | Not documented |
| [24] | Design patterns (Beurer-Kellner et al.) | Architecture (guidance) | Choose a pattern per application (e.g., plan-then-execute, dual LLM) | Not applicable |
| [25] | Xiang et al. (2026) | Position paper | n/a | n/a |
| [26]-[29] | Benchmarks and adaptive-attack evaluations | Evaluation | n/a | Hackett et al. use Unicode tricks (homoglyphs, diacritics, bidi, zero-width) |
| [30] | Al Ghanim et al. (EMNLP 2024) | Evaluation (Arabic) | n/a | Arabizi/transliteration bypasses safety training |

---

## 3. Annotated Sources

### 3.1 Detection classifiers and screening services

#### [1] Meta, "Llama Prompt Guard 2 86M" (model card, 2025)

**Summary.** Prompt Guard 2 is Meta's second-generation classifier for jailbreaks and prompt injections. It comes in an 86M-parameter model built on mDeBERTa-base and a 22M model built on DeBERTa-xsmall. Unlike Prompt Guard 1, it gives a single binary label (benign or malicious) and no longer separates "injection" from "jailbreak." The context window is 512 tokens, and Meta recommends splitting longer inputs into chunks and scanning them in parallel. The card reports an English AUC of 0.998 and 97.5% recall at 1% false-positive rate for the 86M model, about 92 ms latency on an A100, and better AgentDojo results than Prompt Guard 1 and ProtectAI's model. The tokenizer was also changed to resist adversarial tokenization tricks such as whitespace manipulation and fragmented tokens.

**Layer / developer requirements / language.** Runtime input classifier. The developer runs it on every untrusted string (user turns and tool outputs), picks a threshold, and handles chunking; Meta suggests fine-tuning on application data. Supported languages listed on the card: English, French, German, Hindi, Italian, Portuguese, Spanish, and Thai. **Arabic is not listed.**

**Strengths.** Small, fast, open weights, clear evaluation numbers, built-in hardening against tokenizer attacks.
**Limitations.** The card lists "vulnerability to adaptive attacks" as a limitation and presents the model as an additional layer of defense that complements other security measures. The 512-token window means long tool outputs must be split. Independent work bypassed Meta's Prompt Guard with character injection [28] (that paper predates Prompt Guard 2's release) and bypassed "PromptGuard" as packaged in LlamaFirewall [16] with search-based adaptive attacks [29].

**Relevance to Mirsad.** This is the natural open-source baseline for Mirsad's English detector, and the most likely starting checkpoint for an Arabic fine-tune. Because Arabic is missing, Mirsad's Arabic/English detector fills a documented gap, and the chunking rule tells Mirsad how to scan long MCP tool results.

---

#### [2] Protect AI, "Fine-Tuned DeBERTa-v3-base for Prompt Injection Detection" (`deberta-v3-base-prompt-injection-v2`, model card, 2024)

**Summary.** This is a DeBERTa-v3-base binary classifier (0 = benign, 1 = injection) fine-tuned by Protect AI on a mix of public datasets and injections collected from papers, competitions, and community feedback for the LLM Guard project. On a 20,000-prompt held-out set, the card reports 95.25% accuracy, 99.74% recall, and 91.59% precision. The card's example code truncates input at 512 tokens. The card says it does not detect jailbreaks and does not handle non-English prompts. It also warns against running it on system prompts because of false positives. The card now states that the project, and the LLM Guard repository it belongs to, is archived and no longer maintained.

**Layer / developer requirements / language.** Runtime input classifier, Apache-2.0. Same integration pattern as [1]. **English only.**

**Strengths.** Permissive license, widely used baseline, easy to run on CPU.
**Limitations.** Unmaintained; English only; precision of about 92% means noticeable false positives; on AgentDojo the Prompt Guard 2 card [1] reports it far behind newer models. Hackett et al. evaded both v1 and v2 of this model with character-level tricks [28], and Nasr et al. reached over 90% attack success against it with a search attack [29].

**Relevance to Mirsad.** Mirsad's evaluation should include this model as a baseline, since it is the classifier most often used in student and open-source projects. Its English-only scope and archived status support the case for a maintained bilingual detector.

---

#### [3] H. Li, X. Liu, N. Zhang, and C. Xiao, "PIGuard: Prompt Injection Guardrail via Mitigating Overdefense for Free" (ACL 2025)

**Summary.** The paper measures **over-defense**: prompt-guard classifiers flag harmless text as an attack because it contains words common in injections ("ignore," "instructions," and so on). The authors build NotInject, a set of 339 benign sentences packed with such trigger words, and show that leading guard models fall to roughly 60% accuracy on it, close to chance. They then train PIGuard with a strategy called Mitigating Over-defense for Free (MOF), which reduces the trigger-word bias. PIGuard beats the previous best model by 30.4% across their benchmarks, including NotInject. Code, data, and a DeBERTa-based model are public.

**Layer / developer requirements / language.** Runtime input classifier; same integration as [1]. Multilingual support is not discussed.

**Strengths.** Focuses on false positives, which matter for usability and are often ignored. Peer-reviewed, open benchmark. In Nasr et al. [29], PIGuard was the most resistant of the detectors tested (71% attack success, compared with over 90% for the others).
**Limitations.** Still a text classifier, so still bypassable by an adaptive attacker [29]; English-centric.

**Relevance to Mirsad.** Over-defense is a direct concern for Mirsad: every false positive turns into an unnecessary approval request on the user's phone. Mirsad should build an **Arabic NotInject-style benign set** (Arabic text that legitimately uses words like "تجاهل" or "تعليمات") and report false-positive rates alongside detection rates.

---

#### [4] Lakera (Check Point), "Prompt Defense," and [5] "Guard API Endpoint" (vendor documentation)

**Summary.** Lakera Guard is a commercial screening API; after Check Point's agreement to acquire Lakera (announced 16 September 2025) the documentation is branded "Check Point AI Guardrails." The Prompt Defense page says it detects prompt injections and jailbreaks, including attacks hidden in tool responses, retrieved web pages and documents, and malicious tool descriptions, and it can run in Detect (monitor) or Enforce (block) mode. The Guard API page explains the integration: the developer sends an OpenAI-style `messages` array to `POST /v2/guard` at **every** interaction and tool call. `system` and `developer` messages are treated as trusted and are not screened, `tool` messages are screened as untrusted content, assistant `tool_calls` are screened as agent actions, and tool definitions can be screened when an MCP server is added. Only the latest interaction is screened; earlier messages are used as context. The response contains a `flagged` boolean (always `false` in Detect mode) and an optional breakdown. The separate "AI Guardrails" overview page (docs.lakera.ai/docs/defenses) adds four threshold levels modeled on OWASP WAF paranoia levels (L1 Lenient, L2 Balanced, L3 Stricter, L4 Paranoid).

**Layer / developer requirements / language.** Runtime screening service. In the default SaaS deployment the developer must forward conversation content to the vendor's API and set up a project policy; the docs also describe self-hosting (Kubernetes, Docker, or air-gapped) that keeps data in the customer's infrastructure, but only with an enterprise license. The vendor states coverage of "over 100+ major languages and scripts," with Arabic listed under "Arabic and other Semitic languages" (vendor claim, not independently tested).

**Strengths.** The only surveyed product that **documents Arabic coverage**; its role model (trusted system and developer text, untrusted tool text, screened tool calls) matches agent architectures closely; it also screens tool definitions.
**Limitations.** Closed model with no published evaluation methodology; in the SaaS deployment every prompt and tool output leaves the organization, which matters for Saudi data-residency rules (PDPL) and for sensitive enterprise data, and the self-hosted option is limited to enterprise licensees; it is still a probabilistic detector exposed to the adaptive attacks in [27]-[29].

**Relevance to Mirsad.** Lakera's role-based screening model is a useful reference for Mirsad's own trust labels (system and developer content trusted, tool output tainted). Mirsad's open, self-hosted Arabic/English detector plus deterministic policy is a privacy-preserving alternative to sending every tool result to an external SaaS or buying an enterprise self-hosting license. Lakera could also serve as a commercial comparison point if a trial key is available.

---

#### [6] Microsoft, "Prompt Shields in Azure AI Content Safety," and [7] "Region availability and service limits - Azure AI Content Safety" (Microsoft Learn)

**Summary.** Prompt Shields is Microsoft's hosted classifier for two kinds of attack: **user prompt attacks** (jailbreaks, previously called "jailbreak risk detection") and **document attacks** (instructions hidden in emails, documents, or web pages). It defines subtypes for each, such as manipulated content, information gathering, fraud, malware, role-play, and encoding attacks. In Azure AI Foundry it can scan both the user-input and the **tool-response** points of an agent, and it can turn on a preview **Spotlighting** mode that base64-encodes documents so the model treats them as lower-trust (the technique of [10]). The standalone API takes a user prompt of up to 10K characters plus up to five documents totaling 10K characters. The service-limits page [7] states that Prompt Shields "were tested with English only." They may work in other languages, but quality can vary, and Microsoft tells customers to do their own testing.

**Layer / developer requirements / language.** Runtime SaaS screening plus an optional prompt-level transform. The developer either calls the API with prompts and documents or attaches a Foundry guardrail to a deployment or agent. **Tested in English only.**

**Strengths.** Clear attack taxonomy; native support for screening tool responses; Spotlighting packaged as a product feature.
**Limitations.** The English-only testing statement is a gap for Arabic deployments; per-call size limits mean long tool outputs must be split; it is closed; Hackett et al. evaded Azure Prompt Shield with character injection [28].

**Relevance to Mirsad.** Microsoft's own documentation confirms that a major production shield is not validated for Arabic, which directly motivates Mirsad's bilingual detector. The document-attack subtypes are a useful starting taxonomy for labeling Mirsad's Arabic test set.

---

#### [8] Protect AI, "Rebuff: LLM Prompt Injection Detector" (GitHub repository, archived 2025)

**Summary.** Rebuff is an open-source prototype that stacks four detection layers: heuristic filtering of inputs, an LLM that judges whether a prompt is an attack, a vector database of embeddings of earlier attacks for similarity matching, and **canary tokens** placed in the prompt to detect leakage and feed new attacks back into the database. The README says plainly that it is still a prototype and cannot give 100% protection. The repository (Apache-2.0) was archived on 16 May 2025 and is now read-only; the last push was in August 2024.

**Layer / developer requirements / language.** Runtime detector service. The developer must run or call an LLM for the judge layer and maintain a vector store. No language support is documented.

**Strengths.** Shows the defense-in-depth idea early (2023), and its canary-token mechanism is still useful for detecting system-prompt leakage.
**Limitations.** Abandoned; built around screening user prompts and catching prompt leakage, with no notion of tool calls or agent actions; the LLM-judge layer can itself be injected.

**Relevance to Mirsad.** Rebuff is a historical reference point and a reminder that detector-only projects tend to stall. The canary idea can be reused: Mirsad can plant per-session canary strings in sensitive tool results and block any outbound tool call that contains one. This is a cheap, deterministic way to catch exfiltration.

---

#### [9] NAMAA-Space, "Ara-Prompt-Guard_V0" (Hugging Face model card, 2025)

**Summary.** Ara-Prompt-Guard is a community model that adapts Meta's Prompt Guard to Arabic. It is a three-class classifier (safe, injection, jailbreak); the model tree lists Llama-Prompt-Guard-2-86M as its base, although the card text links to the original PromptGuard and calls the base "BERT." It was trained on 33,000 examples (11,000 per class) machine-translated from public English Hugging Face datasets and cleaned with quality scores. The card reports about 97.3% accuracy and about 98% F1 on an Arabic-only test set and says the model is meant for Modern Standard Arabic only. A newer V1 is mentioned on the card.

**Layer / developer requirements / language.** Runtime input classifier (Apache-2.0). **Arabic MSA only**; not tested on dialects, Arabizi, or English.

**Strengths.** Confirms that fine-tuning Prompt Guard for Arabic is feasible with modest compute (the card reports about 30 minutes on two GPUs).
**Limitations.** No paper or peer review; source datasets are not named; evaluation is on a held-out split of the same translated data, which likely overstates real-world accuracy; label names and the base-model description in the card are inconsistent; there is no coverage of Gulf dialects, Arabizi, or code-switching, which [30] shows are exactly the forms that defeat safety training.

**Relevance to Mirsad.** This is the closest prior work to Mirsad's Arabic detector and the baseline Mirsad must beat. The gaps above (dialect, Arabizi, Arabic-English mixing, an independent native-speaker test set, adaptive evaluation) are a concrete research contribution for the team.

---

### 3.2 Prompt-level (marking) defenses

#### [10] K. Hines, G. Lopez, M. Hall, F. Zarfati, Y. Zunger, and E. Kıcıman, "Defending Against Indirect Prompt Injection Attacks With Spotlighting" (CAMLIS 2024)

**Summary.** Spotlighting is a family of prompt-engineering transforms that give the model a continuous signal of where each piece of text came from. There are three variants. *Delimiting* wraps untrusted text in special markers; it is weak because attackers can forge the markers. *Datamarking* interleaves a marker character through the text, for example in place of spaces. *Encoding* turns the text into base64 or a similar encoding and asks the model to decode it, which works only with high-capability models. For delimiting and datamarking, the system prompt tells the model never to follow instructions inside the marked text; for encoding, it tells the model to decode the text and treat it as data. In experiments with GPT-3.5-Turbo, GPT-4, and text-davinci-003, attack success fell from over 50% to under 2% with little loss of task performance.

**Layer / developer requirements / language.** Prompt layer. The developer changes the system prompt and transforms every untrusted document before it enters the context. Microsoft now ships the encoding variant as a preview option in Prompt Shields [6]. Non-English text was not evaluated.

**Strengths.** Zero training; works with closed models; cheap.
**Limitations.** The authors admit they do not fully understand why it works, and they did not test adaptive attackers. Nasr et al. [29] reached over 95% attack success against Spotlighting with a search-based attack, and human red-teamers broke it 265 times. Datamarking that replaces whitespace may behave differently on Arabic script, where word shape and diacritics matter; this has not been studied.

**Relevance to Mirsad.** Mirsad sees tool results before the agent does, so it could apply datamarking to tainted content as an optional extra layer. The review's conclusion is that this should be defense in depth only, never a guarantee, and that Arabic tokenization effects would need to be tested first.

---

### 3.3 Training-time (model-level) defenses

#### [11] E. Wallace, K. Xiao, R. Leike, L. Weng, J. Heidecke, and A. Beutel, "The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions" (arXiv, 2024)

**Summary.** The authors argue that injections and jailbreaks succeed because models give system prompts, user messages, and third-party content the same authority. They define an explicit priority order (system above user above tool or third-party content) and a synthetic data-generation method that teaches the model to follow aligned lower-priority instructions and ignore conflicting ones. Applied to GPT-3.5, the method improved robustness considerably, including against attack types not seen in training, with only minor loss on standard capability benchmarks.

**Layer / developer requirements / language.** Model layer. An agent developer using a hosted API cannot apply it; it is only available if the provider has trained it into the model. Multilingual behavior is not reported.

**Strengths.** Gives the problem a clear conceptual model; improves the base rate of resistance for everyone using the model.
**Limitations.** Probabilistic and opaque to the developer; no guarantees; not reproducible outside OpenAI.

**Relevance to Mirsad.** Mirsad's trust labels (system and developer content trusted, user content semi-trusted, tool output untrusted) mirror this hierarchy, but Mirsad enforces it **outside** the model, at the tool boundary, where it can be checked deterministically. Mirsad works whether or not the underlying model was trained this way.

---

#### [12] S. Chen, J. Piet, C. Sitawarin, and D. Wagner, "StruQ: Defending Against Prompt Injection with Structured Queries" (USENIX Security 2025)

**Summary.** StruQ separates the trusted instruction and the untrusted data into two channels. A front-end formats the prompt and the data with reserved delimiter tokens that the data cannot contain, and the model is fine-tuned to follow only the instruction channel. Training augments a standard instruction-tuning dataset with examples where instructions are planted in the data part, teaching the model to ignore them. The authors report much better resistance to optimization-free injections with little or no utility loss.

**Layer / developer requirements / language.** Model layer plus a front-end formatter. The developer needs an open-weight model they can fine-tune and must route all untrusted data through the data channel. Not evaluated in other languages.

**Strengths.** Draws an analogy to prepared statements in SQL; peer-reviewed at a top security venue; open code.
**Limitations.** Requires retraining, so it does not apply to closed models; the follow-up work [13] showed it remains vulnerable to optimization-based attacks; Nasr et al.'s RL attack succeeded in every StruQ case they tried [29].

**Relevance to Mirsad.** StruQ's message, that untrusted data needs its own channel, is the same idea behind Mirsad's taint labels, but Mirsad applies it in the protocol (MCP and function-call results are tagged as untrusted), not in the model weights. Mirsad stays model-agnostic.

---

#### [13] S. Chen, A. Zharmagambetov, S. Mahloujifar, K. Chaudhuri, D. Wagner, and C. Guo, "SecAlign: Defending Against Prompt Injection with Preference Optimization" (ACM CCS 2025)

**Summary.** SecAlign turns prompt-injection defense into a preference-learning problem. For each training input that contains an injection, it pairs a "secure" response (answering the real instruction) with an "insecure" one (following the injection), then trains with Direct Preference Optimization using LoRA on open models such as Llama-3-8B-Instruct and Mistral-7B-Instruct. The authors report that attack success falls below 10% even for optimization-based attacks stronger than those seen in training, and InjecAgent attack success falls to 0%, while general utility stays close to the undefended model (MMLU drops by 2-3 points).

**Layer / developer requirements / language.** Model layer. Requires open weights, GPU fine-tuning, and strict use of the instruction/data prompt template at inference. Not evaluated beyond English.

**Strengths.** Strong numbers against gradient-based attacks; reproducible recipe.
**Limitations.** The authors note it only works when instruction and data are clearly separated, cannot reach 100% security, and does not cover multi-turn injections or jailbreaks. The follow-up paper [14] found significant utility loss in agentic tasks.

**Relevance to Mirsad.** If a deployment uses an open model, a SecAlign-style model can sit behind Mirsad as an extra layer. It cannot replace Mirsad, because it gives no guarantee and no audit trail.

---

#### [14] S. Chen, A. Zharmagambetov, D. Wagner, and C. Guo, "Meta-SecAlign: Training LLMs against Prompt Injection for Robust Agents" (arXiv, 2025; v4 2026)

**Summary.** When the authors scaled SecAlign to agent workloads, they found that it costs significant utility on tool-calling and web tasks. Meta-SecAlign fixes this with two training changes: injections are placed at random positions (to avoid shortcut learning), and the model's own responses are used as training targets. The latest version reports near-undefended utility on knowledge, instruction-following, tool-calling, and web-navigation tasks, and better security than SecAlign across six benchmarks including AgentDojo, InjecAgent, and WASP. Experiments in v4 cover Llama-3.1-8B, Llama-3.3-70B, Llama-4-Scout, Qwen3-4B, and Qwen3.6-27B (v1 was titled "Meta SecAlign: A Secure Foundation LLM Against Prompt Injection Attacks").

**Layer / developer requirements / language.** Model layer; developers would use a released secured checkpoint or reproduce the training. Language coverage is not documented.

**Strengths.** First training-time defense aimed at agentic utility; open models.
**Limitations.** Nasr et al. [29] report that a search-based adaptive attack reached 96% attack success against MetaSecAlign on AgentDojo, compared with the 2% reported against static attacks (that evaluation used an earlier version of the paper).

**Relevance to Mirsad.** This is the strongest model-level baseline in 2026, and the gap between its static and adaptive results is the clearest case for Mirsad's position: model hardening lowers the base rate of attacks, and a deterministic tool-boundary check is still needed for the attacks that get through.

---

### 3.4 Runtime guardrail frameworks and monitors

#### [15] T. Rebedea, R. Dinu, M. N. Sreedhar, C. Parisien, and J. Cohen, "NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications with Programmable Rails" (EMNLP 2023 System Demonstrations)

**Summary.** NeMo Guardrails is an open-source toolkit that adds programmable "rails" to an LLM application at runtime, independent of the model. Developers write flows in Colang, a modeling language that mixes natural-language examples with Python-like syntax. Topical rails keep the dialogue on allowed paths, and execution rails call Python actions for moderation, fact-checking, and hallucination checks. Jailbreak and moderation rails ask a separate LLM yes/no questions about inputs and outputs. The paper reports that the chained prompting for dialogue rails costs roughly three times the latency and cost of a normal call, and that the toolkit should not be used as a standalone safety solution.

**Layer / developer requirements / language.** Runtime framework sitting around the chat loop. Developers must learn Colang and write rails and actions. Multilingual use is not discussed in the paper.

**Strengths.** Mature, model-agnostic, open source; separates policy from application code in a way that is easy to read.
**Limitations.** Designed for conversational flows rather than tool-call-level authorization; LLM-based rails are themselves injectable and add latency; Hackett et al. evaded its jailbreak detector [28].

**Relevance to Mirsad.** NeMo shows the value of a separate, declarative policy language. Mirsad applies the same idea at a different point: per-tool, per-parameter rules on MCP and function calls instead of dialogue flows, enforced in code rather than by asking another LLM.

---

#### [16] S. Chennabasappa et al., "LlamaFirewall: An Open Source Guardrail System for Building Secure AI Agents" (arXiv, 2025)

**Summary.** LlamaFirewall is Meta's open guardrail framework for agents. It combines three scanners: PromptGuard 2 [1] for direct and indirect injection; AlignmentCheck, an experimental chain-of-thought auditor in which a large LLM reads the agent's reasoning and actions to spot goal hijacking; and CodeShield, a static analyzer for code produced by coding agents. Developers can also add custom regex or LLM-prompt scanners. On AgentDojo with their setup, attack success went from 17.6% with no guardrail to 7.5% with PromptGuard 2, 2.89% with AlignmentCheck (Llama 4 Maverick), and 1.75% with both, while utility dropped from 47.7% to 42.7%.

**Layer / developer requirements / language.** Runtime framework. The developer assigns scanners to message roles (in the paper PromptGuard scanned user and tool messages, AlignmentCheck scanned assistant messages), chooses a capable guardrail LLM, and tunes thresholds. Language support is inherited from PromptGuard 2 (eight languages, not including Arabic).

**Strengths.** Layered design, open source, and a behavioral check (AlignmentCheck) that does not depend on the injection's wording.
**Limitations.** The authors say AlignmentCheck is experimental, needs a large model to work well, adds significant latency, and can itself be targeted by injection. All of its components are probabilistic. Evaluation is mostly on AgentDojo's standard attack.

**Relevance to Mirsad.** This is the closest open-source relative of Mirsad. Mirsad differs in three ways: (1) it enforces deterministic per-tool, per-parameter policy and taint-to-sink rules rather than relying only on classifiers and an LLM auditor; (2) it escalates uncertain cases to a human through a mobile app; and (3) it keeps a hash-chained audit log. LlamaFirewall's numbers make a good comparison point in Mirsad's AgentDojo evaluation.

---

#### [17] K. Zhu, X. Yang, J. Wang, W. Guo, and W. Y. Wang, "MELON: Provable Defense Against Indirect Prompt Injection Attacks in AI Agents" (ICML 2025)

**Summary.** MELON detects injections from the agent's **behavior** instead of the text. The idea is that once an injection succeeds, the agent's next action depends on the injected task more than on the user's. MELON re-runs each step with the user's request masked out and compares the tool calls. If the agent still wants to make the same call without the user's request, the call is probably being driven by injected content and is flagged. The paper adds three design refinements to cut false positives and negatives, and reports better attack prevention and utility than earlier defenses on AgentDojo, with a combined variant (MELON-Aug) doing better still.

**Layer / developer requirements / language.** Runtime monitor; requires the ability to re-execute agent steps, which adds model calls. Because it compares tool calls rather than reading text, it is language-agnostic in principle, though no multilingual evaluation is reported.

**Strengths.** Does not depend on the attack's wording; peer-reviewed at ICML.
**Limitations.** Extra inference cost; Nasr et al. [29] reached 76% attack success on Llama-3.3-70B without knowledge of the defense and 95% with full knowledge of the paper and implementation; human red-teamers produced 69 successful attacks against it.

**Relevance to Mirsad.** MELON's behavioral idea (does this tool call follow from the user's request?) can serve as an optional, language-independent second opinion for high-risk tool calls before they are escalated to a human. Its broken adaptive results again show it cannot be the final gate.

---

#### [18] H. Wang, C. M. Poskitt, and J. Sun, "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents" (ICSE 2026)

**Summary.** AgentSpec is a lightweight domain-specific language for runtime constraints on agents. Each rule names a **trigger** (for example `before_action`, `state_change`, or `agent_finish`), a set of **predicates** that must all hold, and one or more **enforcement** actions: `user_inspection` (pause and ask a human), `llm_self_examine`, `invoke_action`, or `stop`. The main prototype hooks into LangChain's agent loop; the paper calls the design framework-agnostic and discusses extensions such as AutoGen and the Apollo autonomous-driving stack. Across code-execution agents, embodied agents, and autonomous driving, the authors report (in the abstract) preventing unsafe executions in over 90% of code-agent cases with millisecond-level overhead. They also show that OpenAI o1 can draft rules (reported as 95.56% precision and 70.96% recall for embodied-agent rules).

**Layer / developer requirements / language.** Runtime policy enforcement. Developers write rules and implement domain predicates (for example `is_destructive_cmd`), and integrate at the framework level (LangChain is the main implementation). Rules are language-independent; no detector is involved.

**Strengths.** Deterministic, cheap, readable; human approval is a first-class enforcement action; peer-reviewed.
**Limitations.** Checks happen only at discrete execution checkpoints, and the authors note it lacks trajectory-based safety analysis; predicates work at the source-code level rather than through data-flow analysis; LLM-generated rules can be too broad or too narrow; it is not designed specifically around prompt injection or taint.

**Relevance to Mirsad.** AgentSpec is strong evidence that a trigger-predicate-enforce rule model with `user_inspection` is practical and low-overhead, which is essentially Mirsad's policy engine plus mobile approval. Mirsad adds what AgentSpec lacks: taint tracking (data-flow awareness), protocol-level (MCP) interception rather than framework hooks, and a tamper-evident audit log.

---

#### [19] T. Shi et al., "Progent: Securing AI Agents with Privilege Control" (arXiv, 2025; v3 2026; first released as "Progent: Programmable Privilege Control for LLM Agents")

**Summary.** Progent applies least privilege to agents. A policy is a list of allow/forbid rules over tool names and argument conditions (exact values, regex, comparisons, set membership), written in JSON Schema. Calls that match no rule are denied by default, and each rule has a fallback: terminate, ask the user, or return an error to the agent. An LLM can draft the initial policy from the user's task and propose updates during execution. The Z3 SMT solver classifies each update as a narrowing (applied automatically) or an expansion (sent to a configurable approver, which may be a human). Progent runs as a library (LangChain middleware, OpenAI Agents SDK wrapper) or as a **proxy** in front of LLM and MCP endpoints. It reports AgentDojo attack success falling from 39.9% to 1.0% and ASB from 70.3% to 3.9%, and 0% on AgentDojo when expansions are manually approved.

**Layer / developer requirements / language.** Runtime policy enforcement. Developers write or review policies and choose an approver; proxy mode needs no agent code changes. Enforcement is deterministic and does not depend on language.

**Strengths.** The closest published design to Mirsad's policy engine: declarative per-tool, per-argument rules, default deny, MCP proxy deployment, and human approval for privilege expansion.
**Limitations.** The authors note that attacks staying within the privileges the task needs (for example, manipulating which product to recommend), and attacks that only change text output, are out of scope; user mistakes in approval weaken guarantees; proxy mode cannot protect built-in tools that bypass MCP; LLM-generated policies missed lookalike malicious tools on ASB. Progent does not track **data flow** (taint), so it cannot tell whether an allowed `send_email` call carries attacker-supplied content.

**Relevance to Mirsad.** Progent validates Mirsad's core bet (deterministic tool-call policy at a proxy) and gives a direct comparison system. Mirsad goes further by tying policy decisions to **taint**. For example, Mirsad can allow `send_email(to=*)` while the session is untainted and require approval once tool output from an untrusted source has entered the context. It also adds Arabic detection and an audit log.

---

### 3.5 System-level and architectural defenses

#### [20] Y. Wu, F. Roesner, T. Kohno, N. Zhang, and U. Iqbal, "IsolateGPT: An Execution Isolation Architecture for LLM-Based Agentic Systems" (NDSS 2025)

**Summary.** IsolateGPT brings operating-system-style isolation to LLM app ecosystems. A trusted **hub**, made up of a non-LLM operator, an LLM planner, and a memory, routes user queries to **spokes**. Each third-party app runs in its own spoke with a separate LLM instance and its own memory. Apps cannot talk to each other directly; all inter-app messages pass through the hub in declared formats, and the user is asked for permission (one-time, session, or permanent) before data sharing, cross-app collaboration, or irreversible actions such as sending email. In the authors' benchmark of 1,598 attacks (20.2% average success against a non-isolated baseline), IsolateGPT raised a permission dialog in 7.6% of cases, each carrying a warning, and its case studies (for example, email-driven exfiltration from a cloud drive) were blocked. Functionality matched the baseline, with under 30% overhead for about three-quarters of queries.

**Layer / developer requirements / language.** Architecture. The platform must be restructured around hub and spokes, and apps must declare their interfaces. Not language-specific.

**Strengths.** Clear least-privilege and isolation model; permission prompts include a risk assessment.
**Limitations.** The authors scope out injections inside a single app (for example, a malicious email read by the email app); security depends on users reading warnings, and they acknowledge permission fatigue.

**Relevance to Mirsad.** IsolateGPT's permission prompts with an attached risk assessment are a model for Mirsad's mobile approval screen. Its scoping-out of intra-app injection is exactly where Mirsad's taint-to-sink rules help.

---

#### [21] F. Wu, E. Cecchetti, and C. Xiao, "System-Level Defense against Indirect Prompt Injection Attacks: An Information Flow Control Perspective" (arXiv, 2024)

**Summary.** The paper treats indirect prompt injection as an information-flow-control (IFC) problem. It proposes an "f-secure" LLM system in which an LLM planner produces structured, executable plans, a rule-based executor runs them, and a security monitor keeps untrusted inputs out of the planning step, so untrusted content can influence data but not which actions are planned. The authors give formal models of conventional and f-secure systems to reason about the security guarantees, and report through case studies and benchmarks that the design resists attacks while keeping functionality and efficiency.

**Layer / developer requirements / language.** Architecture; requires splitting the agent into planner, executor, and monitor. Not language-specific.

**Strengths.** Early formal IFC treatment of agents; separates "what to do" from "data processed."
**Limitations.** Preprint, not peer-reviewed as of this review; requires reworking the agent; utility depends on planning everything up front.

**Relevance to Mirsad.** Gives Mirsad its vocabulary (sources, sinks, integrity labels) and the argument that untrusted data should never decide which consequential action is taken.

---

#### [22] E. Debenedetti et al., "Defeating Prompt Injections by Design" (CaMeL, arXiv, 2025)

**Summary.** CaMeL wraps a possibly vulnerable LLM in a protective system layer. A **privileged LLM** sees only the user's request and writes a restricted Python program for the task. A **quarantined LLM** without tool access parses untrusted data into fixed schemas. A custom interpreter runs the program, tracks a data-flow graph, attaches **capabilities** (provenance and allowed readers) to each value, and checks **security policies** before every tool call. Because control flow comes only from the trusted request, injected text cannot add new actions, and capabilities stop private data flowing to unauthorized recipients. On AgentDojo, CaMeL completes 77% of tasks with provable security, compared with 84% for an undefended agent.

**Layer / developer requirements / language.** Architecture. The developer adopts the CaMeL interpreter and P-LLM/Q-LLM split, writes security policies as Python functions, and makes tools tag their outputs with capabilities. Token use is about 2.7-2.8 times native tool calling for the median task. Not language-specific.

**Venue note.** The first author's publication list gives the 4th IEEE Conference on Secure and Trustworthy Machine Learning (SaTML 2026) as the venue; the proceedings entry (pages, DOI) was not found, so the arXiv record is cited.

**Strengths.** The strongest security guarantee in the surveyed literature; does not change the model; policies are expressive; open code.
**Limitations.** The authors list several: text-to-text manipulation (for example a biased summary) and phishing are out of scope; side channels remain; users must write and maintain policies; frequent confirmations may lead to fatigue; and in real deployments policy violations are meant to trigger **user confirmation** rather than a hard block. It requires rewriting the agent, which most MCP users cannot do.

**Relevance to Mirsad.** CaMeL is the "gold standard" Mirsad should cite and compare against. Mirsad takes CaMeL's main ideas (provenance labels, policy checks at every tool call, user confirmation on violation) and applies them to **unmodified** agents at the MCP/function-calling boundary. The price is coarser tracking: a proxy cannot see inside the LLM, so once untrusted output enters the context Mirsad must treat everything the agent does afterwards as possibly tainted, in the same conservative way as FIDES [23].

---

#### [23] M. Costa et al., "Securing AI Agents with Information-Flow Control" (FIDES, arXiv, 2025)

**Summary.** The paper gives a formal model of agent planners with information-flow control and identifies which properties dynamic taint tracking can enforce. Its planner, **FIDES**, gives every piece of data a label made of an integrity part (trusted or untrusted) and a confidentiality part (the set of allowed readers), and propagates labels conservatively through model calls. Before each tool call it checks two generic policies: **trusted action** (consequential tools run only from a trusted context) and **permitted flow** (egress tools may send data only to recipients allowed to read it). To keep utility, FIDES can hide tool results in variables that the planner refers to without reading, and can use a constrained, tool-less LLM whose low-capacity outputs (for example a boolean) can be labeled more permissively. On AgentDojo with policies enforced, it blocked all but text-to-text attacks and one calendar case, while completing more tasks than a basic planner.

**Layer / developer requirements / language.** Architecture (planner). Developers must label tools and data sources (for example by reusing existing document classification labels or email sender and recipient metadata; the paper treats MCP annotations only as coarse, possibly unreliable hints) and mark tools as consequential or egress. Not language-specific.

**Strengths.** The clearest formal account of taint tracking for agents; deterministic enforcement; the consequential/egress split maps directly onto real tool catalogs.
**Limitations.** Assumes tools label their outputs correctly; implicit flows through control decisions are not prevented; conservative propagation costs utility; it violates by **aborting** rather than offering a human approval path (the paper notes confirmation fatigue as the reason).

**Relevance to Mirsad.** FIDES is the theoretical basis for Mirsad's taint tracking. Mirsad's per-tool policy can adopt the **consequential vs. egress** classification and the two generic policies almost directly. Where FIDES aborts, Mirsad can route the violation to mobile approval, which turns a utility loss into a human decision that leaves an audit record.

---

#### [24] L. Beurer-Kellner et al., "Design Patterns for Securing LLM Agents against Prompt Injections" (arXiv, 2025)

**Summary.** A group of 14 authors from academia and industry proposes six design patterns that give agents provable resistance to prompt injection: **Action-Selector** (the LLM only picks from fixed actions), **Plan-Then-Execute** (the plan is fixed before untrusted data is read), **LLM Map-Reduce** (isolated LLMs process each untrusted item), **Dual LLM** (a privileged planner never sees untrusted data), **Code-Then-Execute** (the generalization behind CaMeL), and **Context-Minimization**. Ten case studies, including an email assistant, an SQL agent, and a software-engineering agent, show the trade-offs. The authors state that no single pattern fits every threat model.

**Layer / developer requirements / language.** Architecture guidance; developers choose patterns per application.

**Strengths.** Practical and grounded in real application types; candid about utility costs.
**Limitations.** The authors call human confirmation theoretically effective but often burdensome, open to approval fatigue, and easy to fool with obfuscated actions; they say general-purpose agents remain out of reach.

**Relevance to Mirsad.** Mirsad can be described as enforcing a run-time approximation of Plan-Then-Execute: after tainted data enters, new consequential or egress actions need policy permission or human approval. The paper's warnings about confirmation fatigue should shape Mirsad's escalation design (escalate rarely, show the provenance of tainted arguments, and use risk-based defaults).

---

#### [25] C. Xiang et al., "Architecting Secure AI Agents: Perspectives on System-Level Defenses Against Indirect Prompt Injection Attacks" (arXiv position paper, 2026)

**Summary.** This 2026 position paper by eight NVIDIA-affiliated authors (including Kai Greshake; one co-author is also at Johns Hopkins University) argues that system-level defenses should be the "skeleton" of agentic systems. It makes three claims: realistic dynamic tasks require replanning and updating security policies during execution; some context-dependent security decisions still need learned models, but only inside designs that tightly limit what those models see and decide; and in ambiguous cases, personalization and human interaction should be core design considerations. It also warns that current benchmarks can give a false sense of both utility and security.

**Layer / developer requirements / language.** Position / design guidance.

**Strengths.** Recent and synthesizes the field's direction after CaMeL, FIDES, and Progent.
**Limitations.** No system or evaluation; preprint.

**Relevance to Mirsad.** These are close to Mirsad's own design principles: rule-based checks as the skeleton, a constrained model-based detector as a signal, and human approval for ambiguous cases. It is a good citation for justifying the hybrid architecture in the project report.

---

### 3.6 Evaluations: benchmarks, adaptive attacks, and evasion

#### [26] Y. Liu, Y. Jia, R. Geng, J. Jia, and N. Z. Gong, "Formalizing and Benchmarking Prompt Injection Attacks and Defenses" (USENIX Security 2024)

**Summary.** The authors formalize prompt injection, show that earlier attacks are special cases of their framework, and derive a combined attack from it. They benchmark 5 attacks against 10 defenses on 10 LLMs and 7 tasks. Five defenses are prevention-based (paraphrasing, retokenization, delimiters, sandwich prevention, instructional prevention) and five are detection-based (perplexity, windowed perplexity, naive LLM-based detection, response-based detection, known-answer detection). They conclude that no existing defense is sufficient: prevention either fails or hurts clean-task performance, and most detectors either miss many attacks or flag many clean inputs, with known-answer detection the best of a weak set. The open platform is released for future comparisons.

**Layer / developer requirements / language.** Evaluation framework (English tasks).

**Strengths.** A shared vocabulary and benchmark for defenses; open platform.
**Limitations.** Mostly static attacks and single-turn tasks, not tool-using agents.

**Relevance to Mirsad.** Provides the formal definitions and baseline defenses for the report's background chapter. Its known-answer detection idea is similar to the canary approach suggested under [8].

---

#### [27] Q. Zhan, R. Fang, H. S. Panchal, and D. Kang, "Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on LLM Agents" (Findings of NAACL 2025)

**Summary.** The authors test eight indirect-prompt-injection defenses: a fine-tuned DeBERTa detector, an LLM detector, perplexity filtering, instructional prevention, data-prompt isolation, sandwich prevention, paraphrasing, and adversarial fine-tuning. They use InjecAgent with a prompted Vicuna-7B agent and a fine-tuned Llama-3-8B agent. With adaptive versions of GCG and AutoDAN, including a multi-objective variant that also fools the detector and a two-stage variant against paraphrasing, they bypass every defense with over 50% attack success. They conclude that defenses must be evaluated against adaptive attacks before robustness is claimed.

**Layer / developer requirements / language.** Evaluation (English).

**Strengths.** Peer-reviewed, agent-focused, and covers detectors, prompt defenses, and fine-tuning together.
**Limitations.** White-box gradient attacks on open models; mainly affects the agent's first action; smaller gains on AgentDojo's long contexts.

**Relevance to Mirsad.** Direct evidence that Mirsad's detector will be bypassed by a determined attacker, so the policy and taint layer must hold on its own. Mirsad's evaluation plan should include at least one adaptive attack against its own detector (for example a multi-objective attack that targets the Arabic/English classifier score).

---

#### [28] W. Hackett, L. Birch, S. Trawicki, N. Suri, and P. Garraghan, "Bypassing LLM Guardrails: An Empirical Analysis of Evasion Attacks against Prompt Injection and Jailbreak Detection Systems" (LLMSEC 2025)

**Summary.** The paper attacks six deployed detectors: Azure Prompt Shield, ProtectAI v1 and v2, Meta Prompt Guard, NeMo Guard Jailbreak Detect, and Vijil Prompt Injection. It uses two families of evasion. The first is 12 character-injection tricks: emoji and Unicode-tag smuggling, homoglyphs, zero-width characters, bidirectional text, diacritics, full-width text, and others. The second is algorithmic adversarial-ML word perturbations. Emoji smuggling reached 100% evasion against every guardrail on each threat type it was tested on (not every guardrail was tested on both injection and jailbreak), and several other character tricks reached 100% against at least one guardrail. The authors argue the perturbed payloads can still be interpreted by the target LLM but say more rigorous quantitative analysis of this is needed. Word-importance rankings computed on an open-source white-box model (ProtectAI v2) improved transfer to a black-box system (Azure Prompt Shield) for most of the word-level techniques.

**Layer / developer requirements / language.** Evaluation. Non-Latin scripts were not evaluated, but several techniques (diacritics, bidirectional text, zero-width characters) are a natural fit for Arabic script.

**Strengths.** Tests real products; cheap, practical attacks.
**Limitations.** Detector-only evaluation (no end-to-end agent harm); English payloads.

**Relevance to Mirsad.** Very important for the Arabic detector. Arabic text routinely contains diacritics (tashkeel), tatweel (ـ), right-to-left and bidirectional control characters, and letters with lookalike forms. Mirsad's detector must **normalize** input before classification (strip zero-width, tag, and bidi control characters, fold homoglyphs, and normalize Arabic letter variants and diacritics) and should log when normalization changed the input, since that is itself a suspicious signal.

---

#### [29] M. Nasr et al., "The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections" (USENIX Security 2026)

**Summary.** Researchers from OpenAI, Anthropic, Google DeepMind, ETH Zurich, and others argue that most defenses are evaluated against static attack strings or weak optimizers. They scale up four adaptive attack approaches (gradient descent, reinforcement learning, random/search-based optimization, and human red-teaming in a 500-plus-participant competition) against 12 recent defenses. Most fell to over 90% attack success, although most had originally reported near-zero. Examples: Spotlighting and prompt sandwiching above 95%; MetaSecAlign 96%; MELON 95% with full knowledge; StruQ broken in every tested case; and Protect AI, PromptGuard, and Model Armor detectors above 90%, with PIGuard at 71%. The paper also found that stacking several detectors did not stop adaptive attacks, and that many successful triggers did not look malicious, so detectors could not catch them without flagging benign inputs.

**Layer / developer requirements / language.** Evaluation (English).

**Strengths.** The most comprehensive adaptive evaluation to date, by authors from the major labs; peer-reviewed at USENIX Security 2026.
**Limitations.** Different benchmarks per defense, so numbers are not directly comparable; it did not evaluate deterministic system-level designs such as CaMeL or Progent in the same way.

**Relevance to Mirsad.** This is the central citation for Mirsad's architecture argument. Every **probabilistic** layer surveyed (prompt marking, training, detectors, LLM monitors) was broken. What was not evaluated, and what the field increasingly recommends [22]-[25], is deterministic enforcement at the action boundary. Mirsad should therefore present its detector as a **risk signal that drives escalation**, and its policy and taint engine as the **security boundary**.

---

#### [30] M. Al Ghanim, S. Almohaimeed, M. Zheng, Y. Solihin, and Q. Lou, "Jailbreaking LLMs with Arabic Transliteration and Arabizi" (EMNLP 2024)

**Summary.** The authors translate the AdvBench harmful-prompt benchmark into Arabic and test GPT-4 and Claude 3 Sonnet. Prompts in standard Arabic, even with prefix injection, mostly did not produce unsafe output. The same prompts written in **Arabic transliteration** or **Arabizi** (Arabic chat-speak in Latin letters and digits, for example "3" for ع) did. The authors attribute this to the models' learned associations with specific word forms, and call for safety training that covers every form of a language.

**Layer / developer requirements / language.** Evaluation; Arabic-specific.

**Strengths.** Peer-reviewed, Arabic-focused, and shows that alignment does not carry over between scripts.
**Limitations.** Studies jailbreaks rather than indirect injection; two closed models only.

**Relevance to Mirsad.** Evidence that an Arabic detector trained only on MSA (as in [9]) will miss real-world Arabic attacks. Mirsad's Arabic test set should include MSA, Gulf/Najdi dialect, Arabizi, transliteration, and Arabic-English code-switching, and its normalization step should consider Arabizi.

---

## 4. Synthesis

### 4.1 Themes across the literature

**T1. Detectors are useful signals and weak boundaries.** Every classifier surveyed ([1]-[3], [6], [9], plus the detectors inside [15], [16]) reports high accuracy on its own benchmark, and every one tested adaptively was bypassed: by Unicode character tricks with up to 100% evasion [28], by gradient attacks with over 50% success [27], and by search, RL, and human red-teamers with over 90% success in most cases [29]. Stacking detectors did not help [29]. The vendors are open about this: Meta lists vulnerability to adaptive attacks as a Prompt Guard 2 limitation and calls it an additional layer of defense [1], Rebuff admits it cannot give 100% protection [8], and NeMo says it should not be used alone [15]. A second, less discussed problem is **over-defense**: detectors flag benign text that contains trigger words [3], which in an agent with human approval turns into alert fatigue.

**T2. Multilingual coverage is thin, and Arabic coverage is nearly absent.** ProtectAI's model is English-only [2]; Prompt Guard 2 covers eight languages without Arabic [1]; Microsoft says Prompt Shields was tested only in English [7]; PIGuard, Spotlighting, StruQ, SecAlign, NeMo, and LlamaFirewall do not evaluate Arabic. The only Arabic claims come from a closed commercial service (Lakera [4]) and an unreviewed community model limited to MSA and trained on machine-translated data [9]. Meanwhile, research shows that Arabizi and transliteration defeat safety training [30], and Unicode features common in Arabic text (diacritics, bidirectional controls, zero-width joiners) are effective evasion tricks [28].

**T3. Model-level defenses raise the floor but are not under the integrator's control.** Instruction Hierarchy [11], StruQ [12], SecAlign [13], and Meta-SecAlign [14] reduce attack success substantially against static and some optimization attacks, and Meta-SecAlign now keeps agentic utility. They require either the model provider's cooperation or open weights plus GPU fine-tuning, they offer no guarantees, and adaptive attacks still reach 96% against MetaSecAlign [29]. An organization connecting a hosted model to MCP servers cannot use them directly.

**T4. The field is moving toward deterministic enforcement at the action boundary.** From 2024 to 2026 the strongest results come from designs that do not ask "does this text look malicious?" but "is this action allowed given where its inputs came from?": IFC planners (f-secure [21], FIDES [23]), capability interpreters (CaMeL [22]), privilege policies (Progent [19]), rule DSLs (AgentSpec [18]), isolation (IsolateGPT [20]), and the design patterns that generalize them [24], [25]. These designs give provable or near-zero attack success on AgentDojo-style benchmarks, at a cost in utility and engineering effort.

**T5. The cost of system-level defenses is integration and policy-writing effort.** CaMeL needs a custom interpreter and a rewritten agent [22]; FIDES needs a new planner and labeled tools [23]; IsolateGPT needs a hub-and-spoke platform [20]; AgentSpec needs framework hooks and hand-written predicates [18]. Progent's **proxy mode** [19] is the main exception, which shows that MCP-level interception is a realistic way to bring these guarantees to existing agents. Policy authoring is a recurring burden; several papers use LLMs to draft policies [18], [19] but report gaps in the generated rules.

**T6. Human-in-the-loop is everywhere, and its weaknesses are well known.** CaMeL intends policy violations to trigger user confirmation [22]; AgentSpec has a `user_inspection` action [18]; Progent sends privilege expansions to an approver [19]; IsolateGPT asks permission before data sharing and irreversible actions [20]. The same papers, plus [23] and [24], warn about confirmation fatigue, users approving obfuscated actions, and lower automation. None evaluates the approval interface itself.

**T7. Auditability is almost entirely missing.** The surveyed defenses log detections (Lakera's Detect mode [5], Prompt Shields annotations [6], LlamaFirewall scan results [16]), but none provides a **tamper-evident** record of which tool calls were attempted, which data was tainted, which policy fired, and who approved what. Security and compliance teams need that record for incident response and for accountability under frameworks such as the Saudi PDPL and the NCA controls.

**T8. Evaluation practice has changed.** Static attack sets give a false sense of security [27], [29]; benchmarks can mislead about both utility and security [25]; and over-defense must be measured alongside detection [3]. A credible defense in 2026 reports utility and attack success on agent benchmarks such as AgentDojo and InjecAgent, includes at least one adaptive attack, and reports false positives on benign inputs.

### 4.2 Gaps that Mirsad addresses

| Gap in the literature | Evidence | How Mirsad addresses it |
|---|---|---|
| **G1. No validated Arabic injection detection** in open tools; Arabizi, dialect, and Unicode evasion unaddressed | [1], [2], [7], [9], [28], [30] | A bilingual Arabic/English detector with Arabic-aware normalization (diacritics, tatweel, letter variants, zero-width/bidi/tag characters, Arabizi), evaluated on MSA, Gulf dialect, Arabizi, and code-switched data, with a NotInject-style Arabic benign set for false positives |
| **G2. Strong system-level guarantees require rewriting the agent** | [20]-[23] | A drop-in firewall at the MCP and OpenAI function-calling boundary (like Progent's proxy mode [19]); no change to the model or the agent's code |
| **G3. Tool-call policy without data-flow awareness** (Progent, AgentSpec) **or data-flow awareness without a deployable proxy** (FIDES, CaMeL) | [18], [19], [22], [23] | Declarative per-tool, per-parameter policy **combined with** taint labels: tool outputs from untrusted sources taint the session, and taint reaching an egress or consequential sink triggers a policy decision (adopting FIDES's trusted-action and permitted-flow policies [23]) |
| **G4. Detectors used as the gate, despite being broken** | [27]-[29] | The detector only raises risk and triggers escalation; deterministic policy and taint rules are the security boundary, so a bypassed detector does not open a hole by itself |
| **G5. Human approval is assumed but its usability is not designed or evaluated** | [18]-[20], [22]-[24] | A mobile web approval app that is triggered only by policy and taint events, shows the provenance of tainted arguments and the detector's reason, and supports risk-based defaults, so the number of prompts stays low enough to avoid fatigue |
| **G6. No tamper-evident audit trail** of agent actions, policy decisions, and approvals | [5], [6], [16] | A hash-chained, append-only audit log of every intercepted call, taint state, rule match, detector score, and human decision, which can be verified after an incident |
| **G7. Evaluations rely on static attacks** | [25], [27], [29] | Mirsad's evaluation uses AgentDojo (and InjecAgent where possible), includes adaptive attacks on its own detector, and reports utility, attack success, and false-approval-request rates |

### 4.3 Design implications for Mirsad

1. **Adopt FIDES's sink taxonomy.** Classify every tool as *consequential* (changes state), *egress* (sends data outside), both, or neither, and enforce "consequential actions require an untainted context or approval" and "egress requires that all recipients may read the data or approval" [23].
2. **Default deny with explicit allow rules over tool arguments**, as in Progent [19], expressed in a readable format (JSON/YAML Schema-style) so students and administrators can review it.
3. **Taint conservatively.** A proxy cannot see inside the model, so once untrusted tool output enters the context, Mirsad should treat later actions in that session as tainted unless a rule says otherwise. This over-approximation is the same trade-off FIDES makes [23]; utility is recovered through approvals, not by relaxing taint.
4. **Treat the detector as a risk score.** Use Prompt Guard 2 [1] and PIGuard [3] as English baselines, fine-tune an Arabic-capable model, normalize Unicode first [28], and use the score to choose between auto-allow, ask, and block. The score should never on its own allow an action that policy would deny.
5. **Use canaries for exfiltration.** Plant per-session canary tokens in sensitive tool results and block any outbound call that contains one (adapted from [8]).
6. **Design approvals against fatigue.** Show the action, the tainted arguments with their source, and the matched rule, and offer one-time or session scope (following [20]); measure how often prompts are triggered.
7. **Evaluate honestly.** Report results with and without the detector, so the policy layer's guarantees are shown separately from probabilistic detection; include an adaptive attack on the detector [27], [29]; and compare against LlamaFirewall [16] and, if feasible, Progent [19] on AgentDojo.

### 4.4 Limitations of this review

Vendor documentation ([4]-[7]) is a moving target and reflects the vendors' own claims. Several key system-level papers ([19], [21], [23]-[25]) are arXiv preprints with no peer-reviewed version found at the time of writing; CaMeL [22] is listed by its first author as a SaTML 2026 paper, but its proceedings entry was not found, so the arXiv version is cited. Some have several versions with different numbers (CaMeL's v1 and v2 report different AgentDojo results; the current v2 figure is quoted). Numbers from different papers use different benchmarks, models, and attack budgets and should not be compared directly. No source evaluated indirect prompt injection in Arabic end to end; the Arabic evidence comes from jailbreak research [30], a community model card [9], and vendor claims [4].

---

## 5. References (IEEE)

[1] Meta, "Llama Prompt Guard 2 86M," Hugging Face model card, Apr. 2025. [Online]. Available: https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M (accessed Oct. 11, 2026).

[2] ProtectAI.com, "Fine-tuned DeBERTa-v3-base for prompt injection detection (deberta-v3-base-prompt-injection-v2)," Hugging Face model card, 2024. [Online]. Available: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2 (accessed Oct. 11, 2026).

[3] H. Li, X. Liu, N. Zhang, and C. Xiao, "PIGuard: Prompt injection guardrail via mitigating overdefense for free," in *Proc. 63rd Annu. Meeting Assoc. Comput. Linguistics (Vol. 1: Long Papers)*, Vienna, Austria, Jul. 2025, pp. 30420-30437, doi: 10.18653/v1/2025.acl-long.1468.

[4] Lakera (Check Point), "Prompt Defense," *Check Point AI Guardrails (Lakera) Documentation*. [Online]. Available: https://docs.lakera.ai/docs/prompt-defense (accessed Oct. 11, 2026).

[5] Lakera (Check Point), "Guard API endpoint," *Check Point AI Guardrails (Lakera) Documentation*. [Online]. Available: https://docs.lakera.ai/docs/api/guard (accessed Oct. 11, 2026).

[6] Microsoft, "Prompt Shields in Azure AI Content Safety," *Microsoft Learn*, Aug. 2026. [Online]. Available: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection (accessed Oct. 11, 2026).

[7] Microsoft, "Region availability and service limits - Azure AI Content Safety," *Microsoft Learn*, Sep. 2026. [Online]. Available: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/region-availability (accessed Oct. 11, 2026).

[8] Protect AI, "Rebuff: LLM prompt injection detector," GitHub repository (archived May 16, 2025). [Online]. Available: https://github.com/protectai/rebuff (accessed Oct. 11, 2026).

[9] NAMAA-Space, "Ara-Prompt-Guard_V0," Hugging Face model card, 2025. [Online]. Available: https://huggingface.co/NAMAA-Space/Ara-Prompt-Guard_V0 (accessed Oct. 11, 2026).

[10] K. Hines, G. Lopez, M. Hall, F. Zarfati, Y. Zunger, and E. Kıcıman, "Defending against indirect prompt injection attacks with spotlighting," in *Proc. Conf. Applied Machine Learning in Information Security (CAMLIS 2024)*, CEUR Workshop Proceedings, vol. 3920, Arlington, VA, USA, Oct. 2024, pp. 48-62. [Online]. Available: https://ceur-ws.org/Vol-3920/paper03.pdf. (Preprint: arXiv:2403.14720.)

[11] E. Wallace, K. Xiao, R. Leike, L. Weng, J. Heidecke, and A. Beutel, "The instruction hierarchy: Training LLMs to prioritize privileged instructions," arXiv:2404.13208, Apr. 2024. [Online]. Available: https://arxiv.org/abs/2404.13208

[12] S. Chen, J. Piet, C. Sitawarin, and D. Wagner, "StruQ: Defending against prompt injection with structured queries," in *Proc. 34th USENIX Security Symp. (USENIX Security 25)*, Seattle, WA, USA, Aug. 2025, pp. 2383-2400.

[13] S. Chen, A. Zharmagambetov, S. Mahloujifar, K. Chaudhuri, D. Wagner, and C. Guo, "SecAlign: Defending against prompt injection with preference optimization," in *Proc. 2025 ACM SIGSAC Conf. Computer and Communications Security (CCS '25)*, 2025, pp. 2833-2847, doi: 10.1145/3719027.3744836.

[14] S. Chen, A. Zharmagambetov, D. Wagner, and C. Guo, "Meta-SecAlign: Training LLMs against prompt injection for robust agents," arXiv:2507.02735, Jul. 2025 (v4, Sep. 2026). [Online]. Available: https://arxiv.org/abs/2507.02735

[15] T. Rebedea, R. Dinu, M. N. Sreedhar, C. Parisien, and J. Cohen, "NeMo Guardrails: A toolkit for controllable and safe LLM applications with programmable rails," in *Proc. 2023 Conf. Empirical Methods in Natural Language Processing: System Demonstrations*, Singapore, Dec. 2023, pp. 431-445, doi: 10.18653/v1/2023.emnlp-demo.40.

[16] S. Chennabasappa et al., "LlamaFirewall: An open source guardrail system for building secure AI agents," arXiv:2505.03574, May 2025. [Online]. Available: https://arxiv.org/abs/2505.03574

[17] K. Zhu, X. Yang, J. Wang, W. Guo, and W. Y. Wang, "MELON: Provable defense against indirect prompt injection attacks in AI agents," in *Proc. 42nd Int. Conf. Machine Learning (ICML)*, PMLR, vol. 267, 2025, pp. 80310-80329.

[18] H. Wang, C. M. Poskitt, and J. Sun, "AgentSpec: Customizable runtime enforcement for safe and reliable LLM agents," in *Proc. IEEE/ACM 48th Int. Conf. Software Engineering (ICSE '26)*, Apr. 2026, pp. 2938-2950, doi: 10.1145/3744916.3764546.

[19] T. Shi et al., "Progent: Securing AI agents with privilege control," arXiv:2504.11703, Apr. 2025 (v3, May 2026; earlier versions titled "Progent: Programmable privilege control for LLM agents"). [Online]. Available: https://arxiv.org/abs/2504.11703

[20] Y. Wu, F. Roesner, T. Kohno, N. Zhang, and U. Iqbal, "IsolateGPT: An execution isolation architecture for LLM-based agentic systems," in *Proc. Network and Distributed System Security Symp. (NDSS)*, 2025, doi: 10.14722/ndss.2025.241131.

[21] F. Wu, E. Cecchetti, and C. Xiao, "System-level defense against indirect prompt injection attacks: An information flow control perspective," arXiv:2409.19091, Sep. 2024. [Online]. Available: https://arxiv.org/abs/2409.19091

[22] E. Debenedetti et al., "Defeating prompt injections by design," arXiv:2503.18813, Mar. 2025 (v2, Jun. 2025; listed by the first author as appearing at IEEE SaTML 2026, proceedings entry not verified). [Online]. Available: https://arxiv.org/abs/2503.18813

[23] M. Costa et al., "Securing AI agents with information-flow control," arXiv:2505.23643, May 2025 (v2, Sep. 2025). [Online]. Available: https://arxiv.org/abs/2505.23643

[24] L. Beurer-Kellner et al., "Design patterns for securing LLM agents against prompt injections," arXiv:2506.08837, Jun. 2025. [Online]. Available: https://arxiv.org/abs/2506.08837

[25] C. Xiang et al., "Architecting secure AI agents: Perspectives on system-level defenses against indirect prompt injection attacks," arXiv:2603.30016, Mar. 2026. [Online]. Available: https://arxiv.org/abs/2603.30016

[26] Y. Liu, Y. Jia, R. Geng, J. Jia, and N. Z. Gong, "Formalizing and benchmarking prompt injection attacks and defenses," in *Proc. 33rd USENIX Security Symp. (USENIX Security 24)*, Philadelphia, PA, USA, Aug. 2024, pp. 1831-1847.

[27] Q. Zhan, R. Fang, H. S. Panchal, and D. Kang, "Adaptive attacks break defenses against indirect prompt injection attacks on LLM agents," in *Findings Assoc. Comput. Linguistics: NAACL 2025*, Albuquerque, NM, USA, Apr. 2025, pp. 7116-7132, doi: 10.18653/v1/2025.findings-naacl.395.

[28] W. Hackett, L. Birch, S. Trawicki, N. Suri, and P. Garraghan, "Bypassing LLM guardrails: An empirical analysis of evasion attacks against prompt injection and jailbreak detection systems," in *Proc. 1st Workshop on LLM Security (LLMSEC)*, Vienna, Austria, Aug. 2025, pp. 101-114.

[29] M. Nasr et al., "The attacker moves second: Stronger adaptive attacks bypass defenses against LLM jailbreaks and prompt injections," in *Proc. 35th USENIX Security Symp. (USENIX Security 26)*, Baltimore, MD, USA, Aug. 2026, pp. 1467-1486. (Preprint: arXiv:2510.09023.)

[30] M. Al Ghanim, S. Almohaimeed, M. Zheng, Y. Solihin, and Q. Lou, "Jailbreaking LLMs with Arabic transliteration and Arabizi," in *Proc. 2024 Conf. Empirical Methods in Natural Language Processing*, Miami, FL, USA, Nov. 2024, pp. 18584-18600, doi: 10.18653/v1/2024.emnlp-main.1034.

---

## Verification log

Independent fact-check, 11 Oct 2026. Every reference was re-checked against a primary record; nothing was removed.

**What was checked**
- **Bibliographic data.** ACL Anthology BibTeX exports for [3], [15], [27], [28], [30] (authors, titles, venues, cities, months, pages, DOIs all match). USENIX presentation pages and embedded BibTeX for [12] (pp. 2383-2400), [26] (pp. 1831-1847), [29] (pp. 1467-1486, 14 authors). Crossref DOI metadata for [13] (CCS '25, pp. 2833-2847), [18] (ICSE '26, pp. 2938-2950), [20] (NDSS 2025). PMLR page for [17] (vol. 267, pp. 80310-80329). CEUR-WS Vol-3920 index for [10] (pp. 48-62, paper03.pdf; CAMLIS held 24-25 Oct 2024 in Arlington, VA; volume published Feb 2025). arXiv API metadata (titles, author lists, version dates) for [11], [14], [16], [19], [21]-[25] and the preprints of the peer-reviewed papers.
- **Model cards and repositories.** Hugging Face card and API for [1] (created 28 Apr 2025, 8 languages, no Arabic), [2] (archived notice, metrics, limitations, citation author "ProtectAI.com", 2024), [9] (created 29 Apr 2025, base model PG2-86M in metadata, MSA only, V1 announced). GitHub API and page for [8] (created Apr 2023, last push Aug 2024, archived 16 May 2025, Apache-2.0).
- **Vendor documentation.** Lakera/Check Point Prompt Defense, Guard API, AI Guardrails overview, and Self-hosting pages for [4]-[5]; Check Point press release (16 Sep 2025). Microsoft Learn Prompt Shields page (ms.date 28 Aug 2026) and Region availability and service limits page (ms.date 18 Sep 2026) for [6]-[7], including the "tested with English only" statement and the 10K-character / five-document limits.
- **Summaries.** Numerical and qualitative claims were checked against abstracts and full text (arXiv HTML or publisher PDF) for [1]-[3], [10], [13], [15]-[30].

**What was changed**
- [4]-[5] Lakera: the docs describe a self-hosted deployment (Kubernetes, Docker, air-gapped) for enterprise licensees, so "SaaS-only" and "every prompt leaves the organization" were corrected; the claim "only text is screened" was removed (the docs index lists an Audio Defense guardrail page); the acquisition is now described as an agreement announced 16 Sep 2025; the L1-L4 threshold levels are now attributed to the separate AI Guardrails overview page.
- [1] Prompt Guard 2: the card does not say "not a complete solution"; reworded to its "vulnerability to adaptive attacks" limitation and "additional layer of defense" wording. Clarified which Prompt Guard version [28] and [29] attacked.
- [2] ProtectAI: the 512-token figure comes from the card's example code (truncation), not a stated model limit.
- [9] Ara-Prompt-Guard: noted that the card text (base "BERT", link to PromptGuard v1) contradicts the model-tree metadata (PG2-86M).
- [14] Meta-SecAlign: the v4 model list is Llama-3.1-8B, Llama-3.3-70B, Llama-4-Scout, Qwen3-4B, and Qwen3.6-27B; added the v1 title.
- [17] MELON: the 76% figure (not the 95% one) is the one tied to Llama-3.3-70B in [29].
- [18] AgentSpec: LangChain is the main implementation, not the only one (the paper discusses AutoGen and Apollo); limitation reworded to the authors' "trajectory-based safety analysis" wording.
- [22] CaMeL: added the SaTML 2026 venue listed on the first author's site, marked unverified in proceedings; Section 4.4 updated.
- [23] FIDES: the paper treats MCP annotations as coarse, unreliable hints, not as a label source developers can rely on.
- [25] Xiang et al.: replaced "NVIDIA researchers and Kai Greshake" with the actual affiliations (all eight authors are NVIDIA-affiliated, one via a footnote; one also lists Johns Hopkins).
- [28] Hackett et al.: the 100% emoji-smuggling result applies per tested threat type; payload usability was not measured quantitatively; the white-box ranking used ProtectAI v2 against Azure Prompt Shield.
- [10] reference: added the conference month (Oct. 2024).

**Not independently confirmable.** Lakera's 100+ language and Arabic coverage, and all vendor accuracy figures, are vendor claims. No peer-reviewed venues were found for [11], [14], [16], [19], [21], [23]-[25] (DBLP was unreachable during the check; arXiv records and web searches were used instead).
