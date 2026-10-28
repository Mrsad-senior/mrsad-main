# Literature Review Track: Prompt-Injection Attacks and Agent-Security Benchmarks

**Project:** Mirsad (مرصاد), a runtime security firewall for LLM agents and their tools
**Course:** IS499 Senior Project, Prince Sultan University, 2026-2027
**Track:** Prompt-injection attacks and agent-security benchmarks
**Prepared:** 11 October 2026
**Sources:** 31 references (peer-reviewed papers, arXiv preprints, official government/standards pages, and practitioner blogs), numbered in IEEE style in the order of the annotated entries.

> **Verification note.** Every reference below was checked on 11 Oct 2026 against a reachable primary record: the arXiv abstract page, ACL Anthology, USENIX, NeurIPS/ICLR/AAAI proceedings pages, Crossref DOI metadata, NIST/NVD, OWASP, or the author's own blog. Bibliographic details that could not be confirmed (for example, page numbers for preprints) are left out instead of guessed. Numbers quoted from papers are the values reported by the authors, and several papers report slightly different figures in different tables or versions; where that happens it is flagged. An independent second-pass check was carried out on the same date; its corrections are listed in the Verification log at the end of this document.

---

## 1. Introduction

Prompt injection is the main security problem that Mirsad is built to address. Applications that wrap a large language model (LLM) place trusted developer instructions and untrusted text (user input, web pages, e-mails, documents, tool outputs) into one context window. Today's models have no reliable way to tell the two apart, so text that looks like an instruction can take control of the model's behavior. While LLMs only produced text, the main harms were embarrassing or misleading output. Agents that call tools through the Model Context Protocol (MCP) or OpenAI-style function calling raise the stakes: a hijacked agent can read private files, send e-mails, move money, push code, or run shell commands. This track reviews the attack literature from the first public descriptions in 2022 to MCP-specific studies in 2025-2026, along with the benchmarks the community uses to measure agent vulnerability: BIPIA, InjecAgent, AgentDojo, ASB, WASP, MCPTox, MSB, and the NIST/UK AISI red-teaming results. Three questions guide the review: (1) what attack classes exist and how they reach an agent's tools, (2) how robust current models and defenses are when measured honestly, including against adaptive attackers, and (3) which gaps a tool-boundary firewall with declarative policy, taint tracking, a bilingual (Arabic/English) detector, human-in-the-loop (HITL) approval, and a tamper-evident audit log can fill.

---

## 2. Attack Taxonomy

The literature classifies prompt-injection attacks along three mostly independent axes: the **channel** that carries the malicious text, the **goal** the attacker wants to achieve, and the **technique** used to make the model comply.

### 2.1 By channel: direct vs. indirect (and tool-metadata) injection

| Channel | Who supplies the malicious text | Typical carriers | Key sources |
|---|---|---|---|
| **Direct prompt injection** | The attacker is the user of the application and types the payload into the prompt. | Chat box, API input, form fields | [1], [2], [4], [6], [30] |
| **Indirect prompt injection (IPI)** | A third party plants instructions in data that the application later retrieves; the victim user never sees them. | Web pages, e-mails, calendar invites, documents, RAG/vector stores, GitHub issues, tool/API responses | [3], [9], [11], [12], [14], [21], [23], [28] |
| **Tool-metadata injection ("tool poisoning")** | A malicious or compromised MCP server places instructions in tool names, descriptions, or schemas that the model reads but the user usually does not. Variants include *shadowing* (one server's description changes how the agent uses another server's trusted tool) and *rug pulls* (a description changes after the user approved it). | MCP `tools/list` metadata | [22], [25], [26], [27] |

Direct injection is mainly a risk to the application owner (prompt theft, free use of the model, policy bypass). Indirect injection is a risk to the *user*: the attacker borrows the user's own privileges, data, and tools. That makes IPI the central threat for Mirsad. Willison [7] also separates prompt injection (an attack on an *application*, which mixes untrusted input with trusted instructions) from *jailbreaking* (an attack on the *model's* safety training). The two are related but need different defenses.

### 2.2 By attacker goal

| Goal | Description | Example evidence | Mirsad control that applies |
|---|---|---|---|
| **Goal hijacking** (prompt hijacking, agent hijacking) | Redirect the model from the user's task to an attacker-chosen task. | Named in [2]; benchmarked in [6], [8]; "agent hijacking" in [17], [20] | Per-tool/per-parameter policy; detector on tool outputs |
| **Prompt leaking** (prompt extraction) | Make the model reveal its hidden system prompt or configuration, which may be intellectual property or contain secrets. | [1], [2], [4], [6] | Detector; policy forbidding system-prompt content in outbound arguments |
| **Data exfiltration** | Make the agent read private data and send it to an attacker-reachable sink: an HTTP request, an auto-loaded Markdown image URL, an e-mail, a public pull request. | [3], [5], [11] ("data stealing"), [21], [23], [28] | **Taint tracking** from private/untrusted sources to external sinks; HITL approval |
| **Tool misuse / unauthorized actions** | Make the agent call legitimate tools with harmful arguments: transfer money, delete files, make a private repository public, run a downloaded script, send phishing e-mail. | [5], [11] ("direct harm"), [12], [13], [17], [24], [26] | Declarative parameter policy (allow-lists, value constraints); HITL for high-risk calls |
| **Other goals** | Content manipulation and disinformation, denial of service, self-propagating "worm" injections, memory/RAG poisoning for persistence, plan-level backdoors. | [3], [13], [24] | Audit log for forensics; treating memory writes as sinks |

### 2.3 By technique

- **Handcrafted instruction overrides:** "ignore previous instructions", escape characters, fake task completion, and combinations of these [1], [2], [8]. InjecAgent's "enhanced" setting adds a fixed "IMPORTANT!!! Ignore all previous instructions" prefix [11]; AgentDojo's headline baseline is a similar "important message" template [12].
- **Context partitioning:** HouYi injects text that makes the model believe the previous context has ended, then delivers the payload [4].
- **Optimization-based and adaptive attacks:** gradient search (GCG), AutoDAN, reinforcement learning, random search, and human red-teaming tuned against a specific defense [15], [16], [17].
- **Concealment:** the attack performs a harmful tool action while the final chat response looks normal [19].
- **Obfuscation and language shifts:** transliteration, chatspeak (Arabizi), and other encodings that slip past filters trained on standard text [31]; Markdown tricks that bypass link redaction [28].
- **Protocol-level tricks (MCP):** tool-name collisions, preference manipulation, user-impersonating responses, false error messages, and retrieval injection [27]; hidden instructions in tool descriptions [22], [26].

---

## 3. Annotated Sources

### 3.1 Origins and foundational attacks (2022-2023)

#### [1] Willison, "Prompt injection attacks against GPT-3" (2022)

**Reference:** S. Willison, "Prompt injection attacks against GPT-3," *Simon Willison's Weblog*, Sep. 12, 2022. [Online]. Available: https://simonwillison.net/2022/Sep/12/prompt-injection/

**Summary.** This post gave the attack class its name. It builds on Riley Goodside's demonstration that a GPT-3 translation prompt could be overridden by an input that told the model to ignore its directions and print a fixed phrase. Willison compares the problem to SQL injection: developers build prompts by concatenating trusted instructions with untrusted input, and the model cannot tell where one ends and the other begins. He also shows that the same trick can expose the developer's hidden prompt, so prompt leaking is part of the story from the start. He suggests a real fix might resemble parameterized queries, with instructions and data passed in separate channels, but says he does not know whether this is feasible; an April 2023 update to the post adds that it looks extremely difficult, if not impossible, with current LLM architectures.

**Strengths:** Clear first articulation; the SQL-injection analogy makes the problem easy for security people to grasp; widely cited.
**Limitations:** Blog post, not peer reviewed; written before tool-using agents, so it considers text output only.
**Relevance to Mirsad:** Sets out Mirsad's founding assumption. If the model cannot separate data from instructions, enforcement has to sit *outside* the model. Mirsad's deterministic checks on tool calls play the role of the "parameterized query" that the model itself cannot provide.

#### [2] Perez & Ribeiro, "Ignore Previous Prompt" (2022)

**Reference:** F. Perez and I. Ribeiro, "Ignore previous prompt: Attack techniques for language models," presented at the NeurIPS ML Safety Workshop, 2022, arXiv:2211.09527. [Online]. Available: https://arxiv.org/abs/2211.09527

**Summary.** The paper introduces PromptInject, a framework that builds adversarial prompts from masked, interchangeable parts so that attacks can be generated and measured systematically. The authors use it against GPT-3 and define two attack goals that later work adopts: *goal hijacking*, where the model drops its intended task and produces attacker-chosen output, and *prompt leaking*, where the model reveals its own instructions. Simple handcrafted inputs are often enough to succeed. The authors argue that this creates a long tail of risk from attackers with little skill.

**Strengths:** First systematic, quantitative study; vocabulary (goal hijacking, prompt leaking) that later papers reuse.
**Limitations:** Direct injection only; one model family (GPT-3); workshop paper; no tools or agents.
**Relevance to Mirsad:** Goal hijacking and prompt leaking are two of the attack classes in Mirsad's threat model. PromptInject-style templates (rogue strings, override phrases) are a natural seed for the English half of Mirsad's detector test set and can be translated for the Arabic half.

#### [3] Greshake et al., "Not What You've Signed Up For" (AISec 2023)

**Reference:** K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," in *Proc. 16th ACM Workshop Artif. Intell. Secur. (AISec '23)*, Copenhagen, Denmark, 2023, pp. 79-90, doi: 10.1145/3605764.3623985.

**Summary.** This is the paper that defined *indirect* prompt injection. The attacker never talks to the model; they plant instructions in content that an LLM-integrated application will retrieve later. The authors argue that retrieval blurs the line between data and instructions, so retrieved text can act much like executable code. They build a security taxonomy of the consequences, including data theft, self-propagating "worm" injections, and contamination of the wider information ecosystem. They demonstrate the attacks on Bing's GPT-4-based chat, on code-completion tools, and on synthetic GPT-4 applications, showing that injected text can steer which external APIs an application calls.

**Strengths:** Seminal and peer reviewed; shows attacks on real production systems; broad threat taxonomy.
**Limitations:** Demonstrations are mostly qualitative, with no benchmark or success rates; mitigations are left open; the systems tested have since changed.
**Relevance to Mirsad:** Defines the exact threat Mirsad targets. The "retrieved data acts as code" insight is the reason Mirsad attaches a taint label to every tool output that comes from an untrusted source and carries that label forward to later tool calls.

#### [4] Liu et al., HouYi: "Prompt Injection attack against LLM-integrated Applications" (2023)

**Reference:** Y. Liu *et al.*, "Prompt injection attack against LLM-integrated applications," arXiv:2306.05499, 2023. [Online]. Available: https://arxiv.org/abs/2306.05499

**Summary.** The authors first study ten commercial LLM-integrated applications and find that existing injection strategies have limited success against them in practice. They then propose HouYi, a black-box attack modeled on classic web injection. It has three parts: a pre-constructed prompt that blends in with the application, an injection component that creates a *context partition* (convincing the model that the earlier context has ended), and the malicious payload. Run against 36 real applications, HouYi found 31 vulnerable, and ten vendors, including Notion, confirmed the findings. Reported impacts include unrestricted use of the underlying LLM at the owner's cost and theft of application prompts.

**Strengths:** Real-world scale with responsible disclosure; a structured, reusable attack design.
**Limitations:** Still an arXiv preprint (no peer-reviewed venue found; v3 revised Dec. 2025, and the author list changes between versions); focuses on direct injection into chat-style applications rather than tool-using agents.
**Relevance to Mirsad:** Context-partition patterns (fake "end of document" markers, fake system turns, separator flooding) are a concrete feature class for Mirsad's detector in both languages. Prompt theft also argues for policies that keep system-prompt text out of outbound tool arguments.

#### [5] Rehberger, "Plugin Vulnerabilities: Visit a Website and Have Your Source Code Stolen" (2023)

**Reference:** J. Rehberger, "Plugin vulnerabilities: Visit a website and have your source code stolen," *Embrace The Red* (blog), Jun. 20, 2023. [Online]. Available: https://embracethered.com/blog/posts/2023/chatgpt-plugin-vulns-chat-with-code/

**Summary.** Rehberger reviewed approved ChatGPT plugins that used OAuth to act on the user's behalf. He counted 51 OAuth plugins among 445 approved ones and found several open to what he calls cross-plugin request forgery. In his demonstration, a malicious web page read by ChatGPT used prompt injection to make a GitHub-connected plugin create repositories, read private code, and change private repositories to public. He also notes that OpenAI's plugin store criteria require plugins to ask for user confirmation before taking actions, but that the review process did not appear to enforce this.

**Strengths:** A concrete, end-to-end tool-misuse exploit against a production plugin ecosystem; reported to OpenAI (repeatedly, by the author's account) and to plugin developers.
**Limitations:** Practitioner blog, not peer reviewed; the ChatGPT plugin platform has since been retired; little quantitative data beyond plugin counts.
**Relevance to Mirsad:** The plugin ecosystem is a direct ancestor of MCP. The missing confirmation step is exactly what Mirsad's HITL approval provides. A per-parameter rule (for example, forbidding `visibility=public` on repository-update tools, or requiring approval for it) would have stopped this attack whatever the model did.

#### [6] Toyer et al., "Tensor Trust" (ICLR 2024)

**Reference:** S. Toyer, O. Watkins, E. Mendes, J. Svegliato, L. Bailey, T. Wang, I. Ong, K. Elmaaroufi, P. Abbeel, T. Darrell, A. Ritter, and S. Russell, "Tensor Trust: Interpretable prompt injection attacks from an online game," in *Proc. 12th Int. Conf. Learn. Represent. (ICLR)*, 2024. [Online]. Available: https://proceedings.iclr.cc/paper_files/paper/2024/hash/519c51529c3544b3430bd8b17d400365-Abstract-Conference.html

**Summary.** The authors collected attacks and defenses through an online game. Defenders write prompts that should make the model say "access granted" only when a secret code is entered, and attackers try to force or extract that outcome. The ICLR version reports more than 563,000 attack attempts and 118,000 defense prompts, which the authors describe as the first dataset to contain both human-generated attacks and defenses for instruction-following LLMs (the earlier arXiv version, with 126,000 attacks and 46,000 defenses, called it the largest dataset of human-generated adversarial examples of its kind). From this data they build two robustness benchmarks, for *prompt extraction* and *prompt hijacking*, and show that the human-written strategies are easy to interpret and that some of them carry over to deployed LLM applications.

**Strengths:** Very large, human-generated, publicly released dataset; an objective success criterion (string match); ICLR 2024 spotlight paper (per its OpenReview record).
**Limitations:** The game is a simplified setting (direct injection, single defended prompt, no tools); English only; dataset sizes differ between the arXiv and ICLR versions.
**Relevance to Mirsad:** A ready source of labeled English injection strings for training and testing the detector, and its two benchmarks map to Mirsad's hijacking and leaking threat classes. No Arabic equivalent exists, which is a gap Mirsad can help fill (see Section 4).

#### [7] Willison, "Prompt injection and jailbreaking are not the same thing" (2024)

**Reference:** S. Willison, "Prompt injection and jailbreaking are not the same thing," *Simon Willison's Weblog*, Mar. 5, 2024. [Online]. Available: https://simonwillison.net/2024/Mar/5/prompt-injection-jailbreaking/

**Summary.** Willison separates two terms that are often confused. Prompt injection attacks an *application* by mixing untrusted input with a developer's trusted prompt; jailbreaking attacks the safety training of the *model*. He argues that their harms differ: jailbreaks mostly produce embarrassing "screenshot" content, while the damage from prompt injection grows with the data and tools the application can reach. He warns teams not to rely on filters trained against jailbreaks to stop injection.

**Strengths:** Clear terminology that helps scope a project.
**Limitations:** Opinion piece with no empirical evaluation.
**Relevance to Mirsad:** Supports Mirsad's scope statement: it is an injection firewall for tool-using agents, not a content-moderation filter. The detector should be trained and evaluated on *injection* data, not generic jailbreak corpora. It also explains why Arabic jailbreak research [31] is related but not identical evidence.

### 3.2 Formal frameworks and model-level benchmarks

#### [8] Liu et al., "Formalizing and Benchmarking Prompt Injection Attacks and Defenses" (USENIX Security 2024)

**Reference:** Y. Liu, Y. Jia, R. Geng, J. Jia, and N. Z. Gong, "Formalizing and benchmarking prompt injection attacks and defenses," in *Proc. 33rd USENIX Secur. Symp. (USENIX Security 24)*, Philadelphia, PA, USA, Aug. 2024, pp. 1831-1847. [Online]. Available: https://www.usenix.org/conference/usenixsecurity24/presentation/liu-yupei

**Summary.** The paper models an attack as turning the data of a *target task* into compromised data that carries an *injected task*. It shows that earlier attacks (naive, escape characters, context ignoring, fake completion) are special cases of this framework, and it composes them into a stronger "combined attack." The authors evaluate 5 attacks and 10 defenses, split into prevention (paraphrasing, retokenization, delimiters, sandwich, instructional) and detection (perplexity-based, LLM-based, response-based, known-answer), across 10 LLMs and 7 NLP tasks. They find that every attack works, that the combined attack is strongest, and that no defense is adequate: prevention either fails or hurts normal performance, and detection either misses attacks or raises many false alarms. They release the Open-Prompt-Injection toolkit.

**Strengths:** Peer reviewed at a top security venue; a shared formal vocabulary; a large, reproducible benchmark with public code.
**Limitations:** Uses classic NLP tasks (sentiment, spam, summarization) rather than agents with tools; attacks are static rather than adaptive.
**Relevance to Mirsad:** Provides the formal language (target task vs. injected task) for Mirsad's threat-model chapter. The finding that detection-only defenses either miss attacks or flood users with false positives is direct evidence for Mirsad's layered design, where the detector *feeds* policy and HITL decisions instead of being the only gate.

#### [9] Yi et al., BIPIA (KDD 2025)

**Reference:** J. Yi, Y. Xie, B. Zhu, E. Kiciman, G. Sun, X. Xie, and F. Wu, "Benchmarking and defending against indirect prompt injection attacks on large language models," in *Proc. 31st ACM SIGKDD Conf. Knowl. Discov. Data Min. V.1 (KDD '25)*, Toronto, ON, Canada, 2025, pp. 1809-1820, doi: 10.1145/3690624.3709179.

**Summary.** BIPIA is presented as the first benchmark for indirect prompt injection. It covers five application scenarios (e-mail QA, web QA, table QA, summarization, and code QA) with separate text and code attack sets, and the authors find all 25 LLMs they tested vulnerable. They trace the weakness to two causes: models cannot tell informational context from instructions they should act on, and they do not know they should avoid executing instructions found in external content. They propose black-box defenses based on *boundary awareness* and *explicit reminders* (border strings, in-context examples, multi-turn formatting) and a white-box defense that fine-tunes with special boundary tokens. The white-box version reduces attack success to near zero while keeping output quality.

**Strengths:** Peer reviewed; covers several realistic content types; public code and data; a clear causal explanation.
**Limitations:** Tasks are text generation, not tool execution, so success is judged on output text; the strongest defense needs access to model weights, which hosted APIs do not allow; no adaptive attacks.
**Relevance to Mirsad:** Mirsad sits outside the model, so the white-box defense is not available to it, but boundary marking is. Mirsad can wrap untrusted tool outputs in explicit delimiters and provenance tags before returning them to the agent. BIPIA's e-mail and web content is useful test material for the detector.

#### [10] Wallace et al., "The Instruction Hierarchy" (2024)

**Reference:** E. Wallace, K. Xiao, R. Leike, L. Weng, J. Heidecke, and A. Beutel, "The instruction hierarchy: Training LLMs to prioritize privileged instructions," arXiv:2404.13208, 2024. [Online]. Available: https://arxiv.org/abs/2404.13208

**Summary.** The OpenAI authors argue that a root cause of both injection and jailbreaks is that models give a developer's system message the same weight as text from users or third-party tools. They define an *instruction hierarchy* that says how a model should behave when instructions of different privilege conflict, and a synthetic-data method that trains the model to ignore lower-privileged instructions that conflict with higher ones. Applied to GPT-3.5, the method greatly improves robustness, including against attack types not seen in training, with little loss in general capability.

**Strengths:** A principled, model-level defense that targets the root cause; generalizes beyond the training attacks.
**Limitations:** Only the model vendor can apply it; evaluated on one model family; no formal guarantee; still an arXiv preprint (its OpenReview record shows it as a submission to ICLR 2025, not an accepted paper). Later work shows that agents built on models with instruction-hierarchy training still follow simple injections [14], and adaptive attacks bypass training-based defenses with a similar aim, such as StruQ and MetaSecAlign [16].
**Relevance to Mirsad:** The hierarchy (system > user > tool output) is the model-side twin of Mirsad's taint labels. Mirsad enforces the same priority at the tool boundary, deterministically and for any model, so a team can use it even when the underlying LLM does not follow the hierarchy reliably.

### 3.3 Agent-security benchmarks

#### [11] Zhan et al., InjecAgent (Findings of ACL 2024)

**Reference:** Q. Zhan, Z. Liang, Z. Ying, and D. Kang, "InjecAgent: Benchmarking indirect prompt injections in tool-integrated large language model agents," in *Findings Assoc. Comput. Linguist.: ACL 2024*, Bangkok, Thailand, Aug. 2024, pp. 10471-10506, doi: 10.18653/v1/2024.findings-acl.624.

**Summary.** InjecAgent is presented by its authors as the first benchmark built specifically for indirect injection against tool-using agents. It has 1,054 test cases that combine 17 user tools with 62 attacker tools. Attacks fall into two groups: *direct harm* (financial, physical, or data-security damage through a tool) and *data stealing* (first extract private data, then send it to the attacker, for example by e-mail). Tool responses are pre-constructed templates that contain the attacker instruction rather than live executions. Across 30 agents, a ReAct-prompted GPT-4 agent was compromised 24% of the time, and an "enhanced" setting that prepends a fixed "hacking prompt" to the attacker instruction raises success rates further (to 47% for ReAct-prompted GPT-4).

**Strengths:** Peer reviewed; separates action-type harm from exfiltration, including the two-step extract-then-transmit pattern; many models evaluated.
**Limitations:** Single-turn and simulated (no live environment or state); fixed attack templates; English only.
**Relevance to Mirsad:** The two-step data-stealing pattern is precisely the source-to-sink flow that Mirsad's taint tracking is built to break: private data read in step 1 is tainted, and the outbound e-mail in step 2 is blocked or sent for approval. The direct-harm category maps onto Mirsad's per-tool and per-parameter policies.

#### [12] Debenedetti et al., AgentDojo (NeurIPS 2024, Datasets & Benchmarks)

**Reference:** E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, and F. Tramèr, "AgentDojo: A dynamic environment to evaluate prompt injection attacks and defenses for LLM agents," in *Adv. Neural Inf. Process. Syst. 37 (NeurIPS 2024), Datasets and Benchmarks Track*, 2024, pp. 82895-82920, doi: 10.52202/079017-2636.

**Summary.** AgentDojo is an extensible environment rather than a fixed dataset. It has four stateful suites (Workspace, Slack, Travel, and Banking) with 97 user tasks and 629 security test cases, and success is checked by code against the environment state rather than by judging text. The authors find that current models already fail many tasks without any attack, and that attacks succeed often: for GPT-4o under the "important message" attack, targeted attack success is roughly 48-58% depending on the table. Among the baseline defenses evaluated with GPT-4o, a *tool filter* (restricting the agent to tools needed for the task) cut targeted attack success to about 7% while keeping benign utility (73% vs. 69% with no defense), whereas a *prompt-injection detector* reached similar security (about 8%) but cut benign utility from 69% to about 41%, and utility under attack from 50% to 21%, because of false positives.

**Strengths:** Measures utility, utility under attack, and attack success together; designed for plugging in new defenses and adaptive attacks; peer reviewed; adopted by NIST CAISI [17].
**Limitations:** Simulated tools and a limited set of suites; as the authors themselves note, tool filtering fails when the needed tools cannot be planned in advance or when the tools the task needs are also enough for the attack (17% of their test cases); results depend on model version.
**Relevance to Mirsad:** The **primary recommended evaluation harness** for Mirsad. Mirsad can be inserted as a defense in the AgentDojo pipeline and reported on the same three metrics. The detector-versus-utility result is a direct design warning for Mirsad's Arabic/English detector: tune it for a low false-positive rate and combine it with policy instead of blocking on detection alone. The tool-filter result supports Mirsad's declarative least-privilege policy.

#### [13] Zhang et al., Agent Security Bench (ICLR 2025)

**Reference:** H. Zhang, J. Huang, K. Mei, Y. Yao, Z. Wang, C. Zhan, H. Wang, and Y. Zhang, "Agent Security Bench (ASB): Formalizing and benchmarking attacks and defenses in LLM-based agents," in *Proc. 13th Int. Conf. Learn. Represent. (ICLR)*, 2025, arXiv:2410.02644. [Online]. Available: https://arxiv.org/abs/2410.02644

**Summary.** ASB formalizes attacks and defenses across the stages of agent operation and evaluates them in 10 scenarios (for example e-commerce, autonomous driving, and finance) with 10 agents and more than 400 tools. It benchmarks 10 prompt-injection attacks, a memory-poisoning attack, a new "Plan-of-Thought" backdoor, 4 mixed attacks, and 11 defenses on 13 LLM backbones, and introduces a metric that balances utility and security, Net Resilient Performance (NRP). The highest average attack success rate reported is 84.30%, and the authors conclude that current defenses help only a little.

**Strengths:** Wide coverage of attack surfaces beyond the prompt (memory, planning); many backbones; peer reviewed.
**Limitations:** Scenarios and tools are synthetic; backdoors planted before deployment are outside a runtime firewall's reach.
**Relevance to Mirsad:** Shows that injection can enter at several stages. Mirsad guards the tool-invocation stage, and the memory-poisoning result suggests that memory-write and vector-store-insert tools should be treated as *sinks* (where tainted data must not land unchecked) as well as *sources* of taint.

#### [14] Evtimov et al., WASP (NeurIPS 2025, Datasets & Benchmarks)

**Reference:** I. Evtimov, A. Zharmagambetov, A. Grattafiori, C. Guo, and K. Chaudhuri, "WASP: Benchmarking web agent security against prompt injection attacks," in *Adv. Neural Inf. Process. Syst. 38 (NeurIPS 2025), Datasets and Benchmarks Track*, 2025, pp. 22436-22458, doi: 10.52202/085713-0666.

**Summary.** WASP evaluates web-browsing agents end to end in a sandbox derived from VisualWebArena, using GitLab and Reddit environments. Injections are placed only where an ordinary untrusted web user could post content, and attacker goals are concrete security violations. Agents tested include GPT-4o, GPT-4o-mini, o1, and Claude models in the Computer Use reference setup. Even agents with advanced reasoning or instruction-hierarchy training start following simple, human-written injections in up to 86% of cases, but they rarely finish the attacker's full goal (around 17% at most, with slightly different upper bounds in different sections of the paper). The authors call this "security by incompetence."

**Strengths:** A realistic threat model with limited attacker power; separates partial from complete compromise; peer reviewed.
**Limitations:** Web agents only; the low end-to-end success depends on current agent weakness and is likely to rise as agents get better; numbers are tied to specific model versions.
**Relevance to Mirsad:** The gap between "started following the injection" and "completed the attack" shows the value of stopping the *first* unsafe tool call, which is what a tool-boundary firewall does. It also shows that model-level mitigations such as [10] are not enough on their own, so it is reasonable to plan Mirsad around stronger agents in the future.

### 3.4 Adaptive attacks and large-scale red teaming

#### [15] Zhan et al., "Adaptive Attacks Break Defenses Against Indirect Prompt Injection Attacks on LLM Agents" (Findings of NAACL 2025)

**Reference:** Q. Zhan, R. Fang, H. S. Panchal, and D. Kang, "Adaptive attacks break defenses against indirect prompt injection attacks on LLM agents," in *Findings Assoc. Comput. Linguist.: NAACL 2025*, Albuquerque, NM, USA, 2025, pp. 7101-7117, doi: 10.18653/v1/2025.findings-naacl.395.

**Summary.** The authors take eight published IPI defenses (detectors such as a fine-tuned DeBERTa classifier, an LLM-based detector, and perplexity filtering; input-level defenses such as instructional prevention, data isolation, sandwiching, and paraphrasing; and adversarial fine-tuning) and attack each one with methods built for it, including GCG variants and AutoDAN. The main experiments use a 100-case subset of InjecAgent with two open-weight agents (a ReAct-prompted Vicuna-7B and a fine-tuned Llama3-8B), plus a 16-case AgentDojo check in the appendix. On InjecAgent every defense is bypassed, with attack success above 50%; on the AgentDojo subset the adaptive attacks still raise success substantially but less so. The authors conclude that new defenses must be tested against adaptive attackers before anyone trusts their reported robustness.

**Strengths:** Peer reviewed; concrete per-defense attack recipes; public code.
**Limitations:** Small open-weight models and white-box gradient access; partial benchmark subsets.
**Relevance to Mirsad:** Mirsad's detector should be expected to face adaptive attacks once its design is known. This is why Mirsad's security case should rest on deterministic policy and taint-based sink control, which do not depend on recognizing the attack text, with the detector as an extra layer.

#### [16] Nasr et al., "The Attacker Moves Second" (2025)

**Reference:** M. Nasr *et al.*, "The attacker moves second: Stronger adaptive attacks bypass defenses against LLM jailbreaks and prompt injections," arXiv:2510.09023, 2025. [Online]. Available: https://arxiv.org/abs/2510.09023

**Summary.** This 14-author study argues that defenses are usually tested against fixed attack strings or weak optimization, which overstates their strength. The authors scale up four adaptive methods (gradient descent, reinforcement learning, random search, and human-guided exploration) and use them against 12 recent jailbreak and prompt-injection defenses. They bypass all of them, with attack success above 90% for most, even though most of the original papers reported near-zero attack success.

**Strengths:** Large, well-resourced adaptive evaluation; includes human red-teaming, not just automated search; covers many defense styles.
**Limitations:** Preprint; aims to break defenses rather than propose one; the per-defense setup affects how far the results generalize.
**Relevance to Mirsad:** The strongest current evidence that classifier-style and prompt-style defenses cannot be the last line. For Mirsad's evaluation chapter, it argues for including a human red-team phase and reporting results against adaptive attacks, not only against fixed benchmark strings.

#### [17] NIST CAISI, "Strengthening AI Agent Hijacking Evaluations" (2025)

**Reference:** National Institute of Standards and Technology, Center for AI Standards and Innovation (CAISI), "Technical blog: Strengthening AI agent hijacking evaluations," Jan. 17, 2025 (updated Dec. 19, 2025). [Online]. Available: https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations

**Summary.** NIST frames "agent hijacking" as indirect prompt injection and reports experiments on AgentDojo with agents based on an upgraded Claude 3.5 Sonnet. The team fixed framework bugs and added new injection tasks for remote code execution, database exfiltration, and automated phishing, and the agent often carried them out. Red-teaming with the UK AI Security Institute raised attack success from 11% for the strongest baseline attack to 81% for the strongest new attack. Running each attack 25 times instead of once raised average success from 57% to 80%, and per-task results varied widely, so NIST recommends task-level reporting.

**Strengths:** An official government evaluation; practical methodological lessons (adaptive red-teaming, multiple attempts, per-task analysis); open-sourced improvements.
**Limitations:** A blog post rather than a peer-reviewed paper; one model; built on simulated AgentDojo environments.
**Relevance to Mirsad:** The new injection tasks (running downloaded scripts, exfiltrating databases, sending phishing e-mail) are exactly the high-risk sinks that Mirsad's policies should cover: shell execution, database reads followed by network sends, and outbound mail. The multiple-attempt finding means Mirsad's evaluation should report pass@k-style attack success, and its audit log should help spot repeated probing.

#### [18] Zou et al., "Security Challenges in AI Agent Deployment" (2025)

**Reference:** A. Zou *et al.*, "Security challenges in AI agent deployment: Insights from a large scale public competition," in *Adv. Neural Inf. Process. Syst. 38 (NeurIPS 2025), Datasets and Benchmarks Track*, 2025, pp. 88855-88891, doi: 10.52202/085713-2676. (Preprint: arXiv:2507.20526.)

**Summary.** The authors ran a public red-teaming competition against agents powered by 22 frontier LLMs in 44 deployment scenarios. Participants submitted 1.8 million prompt-injection attacks, and more than 60,000 caused policy violations such as unauthorized data access, illicit financial actions, and regulatory noncompliance. The best attacks became the Agent Red Teaming (ART) benchmark, which the arXiv version evaluates on 19 models. Nearly all agents violated policy for most behaviors within 10-100 queries; attacks transferred across models and tasks; and robustness showed little correlation with model size, capability, or inference-time compute.

**Strengths:** Very large scale; realistic deployment policies; a released benchmark; peer reviewed (NeurIPS 2025 Datasets and Benchmarks Track).
**Limitations:** Competition data reflects what participants chose to try; model versions change fast; some figures quoted here (44 scenarios, 19 models, 10-100 queries) come from the arXiv version, and the NeurIPS author list (15 authors) differs from the arXiv one (17).
**Relevance to Mirsad:** The violated "policies" (no unauthorized data access, no unapproved financial action) are the kind of rules Mirsad expresses declaratively per tool and per parameter. Since attackers usually succeed within 10-100 tries, logging and rate-aware monitoring of repeated near-misses in Mirsad's audit trail has real defensive value.

#### [19] Dziemian et al., "How Vulnerable Are AI Agents to Indirect Prompt Injections?" (2026), and [20] NIST CAISI companion blog (2026)

**References:**
[19] M. Dziemian *et al.*, "How vulnerable are AI agents to indirect prompt injections? Insights from a large-scale public competition," arXiv:2603.15714, 2026. [Online]. Available: https://arxiv.org/abs/2603.15714
[20] National Institute of Standards and Technology, Center for AI Standards and Innovation (CAISI), "Insights into AI agent security from a large-scale red-teaming competition," *CAISI Research Blog*, Mar. 23, 2026. [Online]. Available: https://www.nist.gov/blogs/caissi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition (accessed Oct. 11, 2026). (The original `caisi-research-blog` address now redirects here; NIST has since renamed the center CAISSI.)

**Summary.** This paper, summarized by NIST CAISI in [20], reports a public competition hosted by Gray Swan; CAISI, the UK AISI, and several frontier AI labs partnered with Gray Swan on the analysis. The competition focused on *concealed* indirect injection: attacks that trigger a harmful agent action while the final reply to the user shows no sign of it. About 272,000 attempts from 464 participants against 13 frontier models in tool-calling, coding, and computer-use settings produced 8,648 successful attacks across 41 scenarios. Every model was vulnerable, with attack success rates from 0.5% to 8.5%. Some "universal" strategies transferred across 21 of the 41 behaviors and across model families, and robustness correlated only weakly with capability. NIST also notes that attacks found against more robust models transferred to weaker ones more readily than the other way around.

**Strengths:** The most recent large-scale evidence (2026); covers coding and computer-use agents; government involvement; partial data release.
**Limitations:** Preprint with an announced update; per-model numbers are a snapshot; much of the dataset is shared only with labs and government institutes.
**Relevance to Mirsad:** Concealment means the user cannot spot the attack from the chat transcript. Mirsad's independent record of every tool call (hash-chained audit log) and an approval screen that shows the *actual* tool arguments, not the model's description of them, give the visibility that the chat interface lacks.

### 3.5 MCP and agent-ecosystem attacks (2025-2026)

#### [21] Willison, "The Lethal Trifecta for AI Agents" (2025)

**Reference:** S. Willison, "The lethal trifecta for AI agents: private data, untrusted content, and external communication," *Simon Willison's Weblog*, Jun. 16, 2025. [Online]. Available: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/

**Summary.** Willison names three capabilities that, when one agent has all of them, let an attacker steal data: access to private data, exposure to content an attacker can control, and some way to communicate externally (HTTP requests, loaded images, clickable links). Because LLMs follow instructions wherever they appear, an agent with all three can be told to read secrets and send them out. He warns that MCP encourages users to combine tools from different sources, so they can assemble the trifecta without realizing it, and he cites a GitHub MCP exploit as an example. He argues that guardrail products claiming to catch 95% of attacks still fail by web-security standards. For developers he points to recent design-pattern work whose core rule is that an agent that has ingested untrusted input must be constrained so that input cannot trigger consequential actions; for end users who mix tools themselves, he says the only safe course is to avoid the trifecta combination entirely.

**Strengths:** A simple, memorable risk model that practitioners and students can apply; connects directly to MCP practice.
**Limitations:** Blog post; a qualitative heuristic rather than a measured result; it does not deal with harmful actions that involve no data leak (for example, deleting files).
**Relevance to Mirsad:** Mirsad's taint tracking is a way to put this into practice. Once untrusted content has entered the agent's context, Mirsad tracks it and applies stricter policy or HITL approval to any external-communication sink. That breaks the third leg of the trifecta without taking tools away from the user altogether.

#### [22] Beurer-Kellner & Fischer (Invariant Labs), "MCP Security Notification: Tool Poisoning Attacks" (2025)

**Reference:** L. Beurer-Kellner and M. Fischer, "MCP security notification: Tool poisoning attacks," *Invariant Labs Blog*, Apr. 1, 2025. [Online]. Available: https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks

**Summary.** This post introduced *tool poisoning*: an MCP server hides instructions in a tool's description, which the model reads in full but the user usually does not see. In the demonstration, a harmless-looking `add` tool tells the model to read files such as `~/.cursor/mcp.json` and `~/.ssh/id_rsa`, smuggle their contents out through a tool parameter, and keep this from the user; Cursor's confirmation dialog did not show the full arguments. The authors also describe *shadowing*, where one server's description changes how the agent uses a trusted tool from another server (redirecting all e-mails to an attacker), and *rug pulls*, where a server changes a tool's description after approval. Their proposed mitigations are to show users the full tool descriptions, pin tool versions and verify descriptions by hash, and enforce data-flow boundaries between servers.

**Strengths:** Influential first disclosure of an MCP-specific attack class; concrete, reproducible demonstrations; practical mitigations.
**Limitations:** Vendor blog (Invariant sells guardrail products); demonstrations rather than measurements.
**Relevance to Mirsad:** Three direct design implications: (1) tool *metadata* is untrusted input, so Mirsad's detector should scan tool descriptions when servers register; (2) Mirsad can hash and pin each tool description and log changes in its audit chain to catch rug pulls; (3) Mirsad's mobile approval screen must show complete arguments, since a summarized dialog was the weak point in this attack.

#### [23] Milanta & Beurer-Kellner (Invariant Labs), "GitHub MCP Exploited" (2025)

**Reference:** M. Milanta and L. Beurer-Kellner, "GitHub MCP exploited: Accessing private repositories via MCP," *Invariant Labs Blog*, May 26, 2025. [Online]. Available: https://invariantlabs.ai/blog/mcp-github-vulnerability

**Summary.** An attacker opens an issue containing a prompt injection in a public repository. When the owner later asks an agent connected to the official GitHub MCP server to look at open issues, the agent reads the injection, pulls information from the owner's *private* repositories, and publishes it in a pull request on the public repository. The demonstration used Claude 4 Opus in Claude Desktop. The authors call this a "toxic agent flow": no tool is compromised, and the harm comes from combining trusted tools with untrusted input. They note that users often switch tool confirmations to "Always Allow." They recommend fine-grained runtime permissions (for example, one repository per session) and continuous monitoring, and they argue that model alignment alone cannot fix an architectural problem.

**Strengths:** A realistic, high-impact scenario on an official MCP server; a clear account of why patching the server alone does not help.
**Limitations:** Vendor blog; a single case study.
**Relevance to Mirsad:** An ideal demonstration scenario for Mirsad. Taint from the public issue should mark the session, and a policy that restricts each session to one repository (or blocks writes to public repositories once private content is in context) stops the leak. The "Always Allow" habit argues for *risk-based* HITL, where only tainted or high-risk calls go to the phone, to avoid approval fatigue.

#### [24] Radosevich & Halloran, "MCP Safety Audit" (2025)

**Reference:** B. Radosevich and J. Halloran, "MCP safety audit: LLMs with the Model Context Protocol allow major security exploits," arXiv:2504.03767, 2025. [Online]. Available: https://arxiv.org/abs/2504.03767

**Summary.** Using Claude 3.7 and Llama-3.3-70B-Instruct with standard MCP servers (Filesystem, Slack, Everything, Chroma), the authors show that LLMs can be led to use MCP tools against the developer's own machine through malicious code execution, remote-access control, and credential theft. They also describe *retrieval-agent deception* (RADE), in which an attacker plants MCP commands in public data that the victim later adds to a vector database, so a later query retrieves and runs them. They release MCPSafetyScanner, an agentic tool that audits an MCP server and produces a security report.

**Strengths:** Uses real MCP servers; covers host-level harms (code execution, remote access) beyond data leaks; releases a tool.
**Limitations:** The arXiv preprint is the version cited and summarized here (a later version, with authors J. T. Halloran, B. Radosevich, and G. Black, appeared in SPIE's *Assurance and Security for AI-enabled Systems 2026* proceedings, doi: 10.1117/12.3097390); the MCE, RAC, and CT attacks are triggered by directly prompting the model, with RADE as the only indirect variant; few models; case studies rather than a benchmark with success rates.
**Relevance to Mirsad:** Shows that sinks are not only network calls. Writes to the filesystem and changes to configuration are also dangerous, so Mirsad needs per-parameter path policies for filesystem tools. RADE shows that vector stores must be treated as *untrusted sources* for taint purposes.

#### [25] Hou et al., "Model Context Protocol (MCP): Landscape, Security Threats, and Future Research Directions" (2025)

**Reference:** X. Hou, Y. Zhao, S. Wang, and H. Wang, "Model Context Protocol (MCP): Landscape, security threats, and future research directions," *ACM Trans. Softw. Eng. Methodol.*, vol. 35, no. 10, pp. 1-37, 2026, doi: 10.1145/3796519. (Preprint: arXiv:2503.23278.)

**Summary.** This survey (summarized here from arXiv v3, Oct. 2025) describes the MCP server lifecycle in four phases (creation, deployment, operation, maintenance) and 16 activities. It groups security and privacy threats by four kinds of threat source (malicious developers, external attackers, malicious users, and security flaws), covering 16 threat scenarios, with real-world case studies. It proposes safeguards for each phase and outlines research priorities such as standardization and trust boundaries.

**Strengths:** A broad, structured map of the MCP threat landscape; useful for scoping.
**Limitations:** A survey with little empirical measurement; earlier arXiv versions used a different lifecycle (three phases), so the version matters; the MCP ecosystem changes quickly.
**Relevance to Mirsad:** Helps place Mirsad in the *operation* phase of the lifecycle and identify threats it does not cover (for example, supply-chain risks at creation or installation time), which should be stated as out of scope in the project report.

#### [26] Wang et al., MCPTox (AAAI 2026)

**Reference:** Z. Wang, Y. Gao, Y. Wang, S. Liu, H. Sun, H. Cheng, G. Shi, H. Du, and X. Li, "MCPTox: A benchmark for tool poisoning on real-world MCP servers," in *Proc. AAAI Conf. Artif. Intell.*, vol. 40, no. 42, 2026, pp. 35811-35819, doi: 10.1609/aaai.v40i42.40895.

**Summary.** MCPTox measures how well agents resist tool poisoning using 45 live MCP servers and 353 real tools. The authors generate 1,348 malicious test cases (1,312 in the first arXiv version) across 10 risk categories, using three attack templates and few-shot generation. The poisoned tool is never actually called; the harmful action is carried out by *legitimate* tools on the server. Among 20 LLM agents, o1-mini had the highest reported attack success at 72.8%, more capable models were often more vulnerable because they follow instructions better, and refusals were rare (under 3% even for the most cautious model).

**Strengths:** Peer reviewed; real servers and tools; isolates the metadata channel; shows a capability-vulnerability trade-off.
**Limitations:** Focuses on description-based poisoning; test cases are generated from templates; results are a snapshot of 2025 models.
**Relevance to Mirsad:** A ready benchmark for Mirsad's metadata scanning and policy layer. Because the harm happens through legitimate tools, blocking the poisoned tool is not enough. Mirsad's per-parameter rules on the legitimate tools (allowed file paths, allowed recipients) are what actually stop the attack.

#### [27] Zhang et al., MCP Security Bench (ICLR 2026)

**Reference:** D. Zhang, Z. Li, X. Luo, X. Liu, P. Li, and W. Xu, "MCP Security Bench (MSB): Benchmarking attacks against Model Context Protocol in LLM agents," in *Proc. 14th Int. Conf. Learn. Represent. (ICLR)*, 2026, arXiv:2510.15994. [Online]. Available: https://arxiv.org/abs/2510.15994

**Summary.** MSB is an end-to-end benchmark for MCP-specific attacks across the whole tool-use pipeline: planning, invocation, and response handling. It defines 12 attack types, including tool-name collisions, preference manipulation, hidden instructions in descriptions, out-of-scope parameter requests, user-impersonating responses, false-error escalation, tool transfer, retrieval injection, and mixed attacks, and it runs them against real benign and malicious tools over MCP. The evaluation covers 9 LLM agents, 10 domains, 405 tools, and 2,000 attack instances. It reports Net Resilient Performance (NRP), which combines task performance and attack resistance; the metric was introduced in ASB [13], and MSB adapts it by computing it from task performance under attack rather than in benign runs. The authors argue that earlier benchmarks such as AgentDojo, InjecAgent, and ASB cover a narrower range of attacks and do not exercise these MCP-specific risks with real tool execution.

**Strengths:** Peer reviewed; MCP-native with real tool execution; a fine-grained attack taxonomy; a single metric that captures the utility/security trade-off.
**Limitations:** Nine agents; attack instances are constructed by the authors; the ecosystem moves fast.
**Relevance to Mirsad:** Since Mirsad supports both MCP and OpenAI-style function calling, it should be evaluated on MSB as well as AgentDojo. NRP (in MSB's under-attack form) is a good headline metric for the final report. Name-collision attacks argue for Mirsad identifying tools by server-qualified names in its policies.

### 3.6 Real-world incidents and standards

#### [28] Reddy & Gujral, "EchoLeak" (AAAI Symposium Series 2025), and [29] NVD entry CVE-2025-32711

**References:**
[28] P. Reddy and A. S. Gujral, "EchoLeak: The first real-world zero-click prompt injection exploit in a production LLM system," in *Proc. AAAI Symp. Ser.*, vol. 7, no. 1, 2025, pp. 303-311, doi: 10.1609/aaaiss.v7i1.36899.
[29] National Institute of Standards and Technology, "CVE-2025-32711 detail," *National Vulnerability Database*, Jun. 11, 2025. [Online]. Available: https://nvd.nist.gov/vuln/detail/CVE-2025-32711

**Summary.** EchoLeak was a zero-click flaw in Microsoft 365 Copilot: one crafted e-mail, with no action by the victim, could cause Copilot to leak internal data to an attacker. The paper analyzes how the exploit chained several bypasses: it evaded Microsoft's cross-prompt-injection (XPIA) classifier, used reference-style Markdown to get around link redaction, relied on images that the client fetched automatically, and routed data through a Microsoft Teams proxy allowed by the content-security policy. NVD records the issue as CVE-2025-32711 (CWE-74, injection, as assigned by Microsoft), described as AI command injection that lets an unauthorized attacker disclose information over a network; Microsoft scored it CVSS 3.1 9.3 (critical) and NVD 7.5 (high). The authors propose prompt partitioning, stronger input/output filtering, provenance-based access control, and strict content-security policies.

**Strengths:** A documented, CVE-tracked production exploit; a detailed breakdown of the exploit chain; published in the AAAI Symposium Series proceedings (AAAI Fall Symposium 2025).
**Limitations:** A single vendor and incident; the fix was server-side, so outside researchers cannot fully reproduce it; symposium rather than main-conference venue.
**Relevance to Mirsad:** Strong real-world proof that a dedicated injection *classifier* can be bypassed in production, so Mirsad's detector must not be the only control. The proposed "provenance-based access control" is essentially Mirsad's taint tracking. Auto-fetched URLs and images should be treated as external sinks.

#### [30] OWASP, "LLM01:2025 Prompt Injection"

**Reference:** OWASP Gen AI Security Project, "LLM01:2025 prompt injection," in *OWASP Top 10 for LLM Applications 2025*, OWASP Foundation, Nov. 2024. [Online]. Available: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ (accessed Oct. 11, 2026).

**Summary.** OWASP ranks prompt injection as the top risk for LLM applications in the 2025 edition of its list (released in November 2024). It defines direct injection (the user's own input changes model behavior) and indirect injection (external content such as web pages or files does so) and notes that either can be intentional or accidental. Listed impacts include disclosure of sensitive data or system prompts, content manipulation, unauthorized use of functions, arbitrary command execution in connected systems, and manipulated decisions. Recommended mitigations include constraining model behavior, validating output formats with deterministic code, filtering inputs and outputs, enforcing least privilege, requiring human approval for high-risk actions, separating and labeling untrusted content, and adversarial testing.

**Strengths:** A widely recognized industry standard; good for requirements traceability.
**Limitations:** High-level guidance with no evaluation or implementation detail.
**Relevance to Mirsad:** Mirsad implements several OWASP mitigations directly: least privilege (declarative per-tool policy), human approval (mobile HITL), segregation and labeling of untrusted content (taint tracking), input/output filtering (detector), and deterministic validation (parameter constraints). This mapping can be used as a requirements-traceability table in the IS499 report.

#### [31] Al Ghanim et al., "Jailbreaking LLMs with Arabic Transliteration and Arabizi" (EMNLP 2024)

**Reference:** M. Al Ghanim, S. Almohaimeed, M. Zheng, Y. Solihin, and Q. Lou, "Jailbreaking LLMs with Arabic transliteration and Arabizi," in *Proc. 2024 Conf. Empirical Methods Natural Lang. Process. (EMNLP)*, Miami, FL, USA, Nov. 2024, pp. 18584-18600, doi: 10.18653/v1/2024.emnlp-main.1034.

**Summary.** The authors translated the 520 harmful prompts of AdvBench into Arabic and then converted them into two informal forms: transliteration and Arabizi chatspeak (Arabic written with Latin letters and digits). Against GPT-4 and Claude 3 Sonnet, prompts in standard Arabic script were mostly refused, even with prefix-injection tricks, but the transliterated and Arabizi versions produced unsafe answers much more often. The authors attribute this to models learning associations with particular non-standard word forms, and they discuss mitigation for Arabic.

**Strengths:** Peer reviewed; one of the few adversarial studies centered on Arabic; covers the informal ways Arabic is actually written online.
**Limitations:** Studies *jailbreaking*, not prompt injection (see [7]); 2024 models; harmful text output, not tool actions.
**Relevance to Mirsad:** The closest peer-reviewed evidence for Mirsad's bilingual detector. Its main lesson is that a detector checking only Arabic script will miss attacks written in Arabizi or transliteration. Mirsad's normalization pipeline should handle Latin-script Arabic and digit substitutions (for example 3, 7, 2) and mixed Arabic/English text. Our search found no Arabic indirect-injection benchmark, so this paper is the nearest evidence available.

---

## 4. Synthesis

### 4.1 Themes across the literature

1. **The root cause is a missing boundary between data and instructions.** From the first descriptions [1], [2] through the formal treatment [8] and BIPIA's causal analysis [9], every line of work points to the same flaw: models act on instructions wherever they appear. Model-level fixes such as the instruction hierarchy [10] and boundary-token fine-tuning [9] reduce the problem but do not remove it [14], [16].

2. **Agents turn injection from a content problem into an action problem.** Benchmarks have moved from text tasks [8], [9] to tool-using agents [11], [12], [13], to web and computer-use agents [14], [19], and to MCP-native settings [26], [27]. Success is now measured by changes to environment state (money moved, files read, PRs opened), not by output text.

3. **More capable models are not automatically safer.** Several independent studies find that stronger instruction-followers can be *more* exposed [8], [26], [27], and that robustness tracks capability only weakly [18], [19]. Mirsad therefore cannot assume that upgrading the model will solve the problem.

4. **Static evaluation overstates robustness.** Adaptive attacks bypass published defenses at high rates [15], [16]. Red-teaming raised attack success from 11% to 81% in NIST's tests, and 25 attempts per attack raised average success from 57% to 80% [17]. Universal attacks transfer across models [18], [19].

5. **Detectors on their own are fragile; system-level controls work better.** AgentDojo's detector cut benign utility from 69% to about 41% to reach security comparable to a simple tool filter, which kept utility [12]. Detection baselines in [8] either missed attacks or produced many false positives. EchoLeak bypassed a production injection classifier [28]. Willison argues that "95%" detection is a failing grade [21]. In contrast, least privilege and dataflow controls (tool filter [12], per-session repository scoping [23], OWASP mitigations [30]) give large reductions in risk.

6. **MCP widens the attack surface.** Tool metadata becomes an injection channel [22], [26]. Servers can change after approval (rug pulls) or interfere with each other (shadowing) [22]. Official servers can become part of "toxic flows" without containing any bug [23]. MCP also makes it easy for users to assemble the lethal trifecta [21].

7. **Real incidents confirm the research.** Rehberger's plugin exploits [5], the GitHub MCP case [23], and the CVE-tracked EchoLeak [28], [29] show that these attacks work against deployed products, not only in benchmarks.

8. **Almost all evidence is in English.** As far as we could determine, every benchmark reviewed here is in English. The only Arabic adversarial work found [31] studies jailbreaking, and it shows that informal Arabic forms bypass safety training that holds for standard Arabic script.

### 4.2 Gaps that Mirsad addresses

| # | Gap in the literature or in current practice | Evidence | How Mirsad responds |
|---|---|---|---|
| G1 | Defenses inside the model can be bypassed, and teams using hosted APIs cannot retrain models. | [9], [10], [14], [15], [16] | Enforcement at the **tool boundary**, independent of the model, for both MCP and OpenAI-style function calling. |
| G2 | Exfiltration needs a source-to-sink flow, but most deployed agents do not track where data came from. | [11] (data stealing), [21], [23], [28] | **Taint tracking** that marks untrusted and private content and applies policy or approval when it reaches external sinks (HTTP, e-mail, PR/comment creation, image URLs, memory writes). |
| G3 | Tool misuse happens through *legitimate* tools with harmful arguments. | [5], [12], [17], [26] | **Declarative per-tool and per-parameter policy** (allow-lists, value constraints such as allowed recipients, paths, repositories, amounts). |
| G4 | Tool metadata is an unmonitored injection channel, and descriptions can change after approval. | [22], [26], [27] | Scan tool descriptions with the detector when servers register; hash-pin descriptions and log any change in the audit chain (recommended feature). |
| G5 | Confirmation dialogs hide arguments and users fall into "Always Allow" fatigue. | [22], [23] | **Risk-based HITL** on a mobile web app showing full arguments plus taint provenance, and only for tainted or high-risk calls. |
| G6 | Concealed attacks leave no trace in the chat, and benchmarks measure attack success but not accountability after an incident. | [18], [19] | A **tamper-evident, hash-chained audit log** of every tool call, decision, and approval, which supports forensics and detection of repeated probing. |
| G7 | We found no Arabic or Arabizi prompt-injection benchmark in the literature reviewed, and informal Arabic forms bypass safety training. | [6], [9], [31] | A **bilingual Arabic/English detector** with Arabizi and transliteration normalization; the team can contribute a small Arabic IPI test set (for example, Arabic versions of AgentDojo or InjecAgent injection tasks). |
| G8 | MCP-specific attacks are missing from function-calling benchmarks. | [27] | A protocol-agnostic proxy design, evaluated on both function-calling (AgentDojo, InjecAgent) and MCP (MCPTox, MSB) benchmarks. |

### 4.3 Implications for Mirsad's evaluation plan

- **Benchmarks:** Use AgentDojo [12] as the main harness (it accepts plug-in defenses and reports utility, utility under attack, and targeted attack success); InjecAgent [11] for direct-harm vs. data-stealing breakdowns; MCPTox [26] and MSB [27] for MCP-specific attacks, reporting the NRP metric (introduced in ASB [13], in the under-attack form used by MSB [27]).
- **Honest threat model:** Include adaptive attacks against the detector [15], [16], several attempts per attack [17], and per-task results rather than a single average [17].
- **Utility cost:** Report false-positive rate and benign utility alongside security, because a detector that blocks too much is not deployable [8], [12].
- **Arabic coverage:** Build a small Arabic, Arabizi, and mixed-language injection test set, since we found none in the literature reviewed (the closest work [31] studies jailbreaking).
- **Scope statement:** Mirsad covers runtime tool calls. It does not cover training-time backdoors [13], supply-chain compromise when MCP servers are created or installed [25], or harms that happen only in text with no tool call.

### 4.4 Limitations of this review

Several sources are preprints [4], [10], [16], [19], [24] or practitioner and vendor blogs [1], [5], [7], [21]-[23]. For [24] a later peer-reviewed version exists (see its entry), but the preprint is the version summarized. They are included because they are the original or most current record of influential results, and they are marked as such. Attack success rates are tied to specific model versions and will go out of date quickly. Some papers report slightly different numbers in different tables or versions; where this was noticed, the text gives ranges or notes the inconsistency.

---

## 5. References (IEEE)

[1] S. Willison, "Prompt injection attacks against GPT-3," *Simon Willison's Weblog*, Sep. 12, 2022. [Online]. Available: https://simonwillison.net/2022/Sep/12/prompt-injection/

[2] F. Perez and I. Ribeiro, "Ignore previous prompt: Attack techniques for language models," presented at the NeurIPS ML Safety Workshop, 2022, arXiv:2211.09527. [Online]. Available: https://arxiv.org/abs/2211.09527

[3] K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," in *Proc. 16th ACM Workshop Artif. Intell. Secur. (AISec '23)*, Copenhagen, Denmark, 2023, pp. 79-90, doi: 10.1145/3605764.3623985.

[4] Y. Liu *et al.*, "Prompt injection attack against LLM-integrated applications," arXiv:2306.05499, 2023. [Online]. Available: https://arxiv.org/abs/2306.05499

[5] J. Rehberger, "Plugin vulnerabilities: Visit a website and have your source code stolen," *Embrace The Red*, Jun. 20, 2023. [Online]. Available: https://embracethered.com/blog/posts/2023/chatgpt-plugin-vulns-chat-with-code/

[6] S. Toyer, O. Watkins, E. Mendes, J. Svegliato, L. Bailey, T. Wang, I. Ong, K. Elmaaroufi, P. Abbeel, T. Darrell, A. Ritter, and S. Russell, "Tensor Trust: Interpretable prompt injection attacks from an online game," in *Proc. 12th Int. Conf. Learn. Represent. (ICLR)*, 2024. [Online]. Available: https://proceedings.iclr.cc/paper_files/paper/2024/hash/519c51529c3544b3430bd8b17d400365-Abstract-Conference.html

[7] S. Willison, "Prompt injection and jailbreaking are not the same thing," *Simon Willison's Weblog*, Mar. 5, 2024. [Online]. Available: https://simonwillison.net/2024/Mar/5/prompt-injection-jailbreaking/

[8] Y. Liu, Y. Jia, R. Geng, J. Jia, and N. Z. Gong, "Formalizing and benchmarking prompt injection attacks and defenses," in *Proc. 33rd USENIX Secur. Symp. (USENIX Security 24)*, Philadelphia, PA, USA, Aug. 2024, pp. 1831-1847. [Online]. Available: https://www.usenix.org/conference/usenixsecurity24/presentation/liu-yupei

[9] J. Yi, Y. Xie, B. Zhu, E. Kiciman, G. Sun, X. Xie, and F. Wu, "Benchmarking and defending against indirect prompt injection attacks on large language models," in *Proc. 31st ACM SIGKDD Conf. Knowl. Discov. Data Min. V.1 (KDD '25)*, Toronto, ON, Canada, 2025, pp. 1809-1820, doi: 10.1145/3690624.3709179.

[10] E. Wallace, K. Xiao, R. Leike, L. Weng, J. Heidecke, and A. Beutel, "The instruction hierarchy: Training LLMs to prioritize privileged instructions," arXiv:2404.13208, 2024. [Online]. Available: https://arxiv.org/abs/2404.13208

[11] Q. Zhan, Z. Liang, Z. Ying, and D. Kang, "InjecAgent: Benchmarking indirect prompt injections in tool-integrated large language model agents," in *Findings Assoc. Comput. Linguist.: ACL 2024*, Bangkok, Thailand, Aug. 2024, pp. 10471-10506, doi: 10.18653/v1/2024.findings-acl.624.

[12] E. Debenedetti, J. Zhang, M. Balunović, L. Beurer-Kellner, M. Fischer, and F. Tramèr, "AgentDojo: A dynamic environment to evaluate prompt injection attacks and defenses for LLM agents," in *Adv. Neural Inf. Process. Syst. 37 (NeurIPS 2024), Datasets and Benchmarks Track*, 2024, pp. 82895-82920, doi: 10.52202/079017-2636.

[13] H. Zhang, J. Huang, K. Mei, Y. Yao, Z. Wang, C. Zhan, H. Wang, and Y. Zhang, "Agent Security Bench (ASB): Formalizing and benchmarking attacks and defenses in LLM-based agents," in *Proc. 13th Int. Conf. Learn. Represent. (ICLR)*, 2025, arXiv:2410.02644. [Online]. Available: https://arxiv.org/abs/2410.02644

[14] I. Evtimov, A. Zharmagambetov, A. Grattafiori, C. Guo, and K. Chaudhuri, "WASP: Benchmarking web agent security against prompt injection attacks," in *Adv. Neural Inf. Process. Syst. 38 (NeurIPS 2025), Datasets and Benchmarks Track*, 2025, pp. 22436-22458, doi: 10.52202/085713-0666.

[15] Q. Zhan, R. Fang, H. S. Panchal, and D. Kang, "Adaptive attacks break defenses against indirect prompt injection attacks on LLM agents," in *Findings Assoc. Comput. Linguist.: NAACL 2025*, Albuquerque, NM, USA, 2025, pp. 7101-7117, doi: 10.18653/v1/2025.findings-naacl.395.

[16] M. Nasr *et al.*, "The attacker moves second: Stronger adaptive attacks bypass defenses against LLM jailbreaks and prompt injections," arXiv:2510.09023, 2025. [Online]. Available: https://arxiv.org/abs/2510.09023

[17] National Institute of Standards and Technology, Center for AI Standards and Innovation, "Technical blog: Strengthening AI agent hijacking evaluations," Jan. 17, 2025 (updated Dec. 19, 2025). [Online]. Available: https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations

[18] A. Zou *et al.*, "Security challenges in AI agent deployment: Insights from a large scale public competition," in *Adv. Neural Inf. Process. Syst. 38 (NeurIPS 2025), Datasets and Benchmarks Track*, 2025, pp. 88855-88891, doi: 10.52202/085713-2676.

[19] M. Dziemian *et al.*, "How vulnerable are AI agents to indirect prompt injections? Insights from a large-scale public competition," arXiv:2603.15714, 2026. [Online]. Available: https://arxiv.org/abs/2603.15714

[20] National Institute of Standards and Technology, Center for AI Standards and Innovation, "Insights into AI agent security from a large-scale red-teaming competition," *CAISI Research Blog*, Mar. 23, 2026. [Online]. Available: https://www.nist.gov/blogs/caissi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition (accessed Oct. 11, 2026).

[21] S. Willison, "The lethal trifecta for AI agents: private data, untrusted content, and external communication," *Simon Willison's Weblog*, Jun. 16, 2025. [Online]. Available: https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/

[22] L. Beurer-Kellner and M. Fischer, "MCP security notification: Tool poisoning attacks," *Invariant Labs Blog*, Apr. 1, 2025. [Online]. Available: https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks

[23] M. Milanta and L. Beurer-Kellner, "GitHub MCP exploited: Accessing private repositories via MCP," *Invariant Labs Blog*, May 26, 2025. [Online]. Available: https://invariantlabs.ai/blog/mcp-github-vulnerability

[24] B. Radosevich and J. Halloran, "MCP safety audit: LLMs with the Model Context Protocol allow major security exploits," arXiv:2504.03767, 2025. [Online]. Available: https://arxiv.org/abs/2504.03767

[25] X. Hou, Y. Zhao, S. Wang, and H. Wang, "Model Context Protocol (MCP): Landscape, security threats, and future research directions," *ACM Trans. Softw. Eng. Methodol.*, vol. 35, no. 10, pp. 1-37, 2026, doi: 10.1145/3796519.

[26] Z. Wang, Y. Gao, Y. Wang, S. Liu, H. Sun, H. Cheng, G. Shi, H. Du, and X. Li, "MCPTox: A benchmark for tool poisoning on real-world MCP servers," in *Proc. AAAI Conf. Artif. Intell.*, vol. 40, no. 42, 2026, pp. 35811-35819, doi: 10.1609/aaai.v40i42.40895.

[27] D. Zhang, Z. Li, X. Luo, X. Liu, P. Li, and W. Xu, "MCP Security Bench (MSB): Benchmarking attacks against Model Context Protocol in LLM agents," in *Proc. 14th Int. Conf. Learn. Represent. (ICLR)*, 2026, arXiv:2510.15994. [Online]. Available: https://arxiv.org/abs/2510.15994

[28] P. Reddy and A. S. Gujral, "EchoLeak: The first real-world zero-click prompt injection exploit in a production LLM system," in *Proc. AAAI Symp. Ser.*, vol. 7, no. 1, 2025, pp. 303-311, doi: 10.1609/aaaiss.v7i1.36899.

[29] National Institute of Standards and Technology, "CVE-2025-32711 detail," *National Vulnerability Database*, Jun. 11, 2025. [Online]. Available: https://nvd.nist.gov/vuln/detail/CVE-2025-32711

[30] OWASP Gen AI Security Project, "LLM01:2025 prompt injection," in *OWASP Top 10 for LLM Applications 2025*, OWASP Foundation, Nov. 2024. [Online]. Available: https://genai.owasp.org/llmrisk/llm01-prompt-injection/ (accessed Oct. 11, 2026).

[31] M. Al Ghanim, S. Almohaimeed, M. Zheng, Y. Solihin, and Q. Lou, "Jailbreaking LLMs with Arabic transliteration and Arabizi," in *Proc. 2024 Conf. Empirical Methods Natural Lang. Process. (EMNLP)*, Miami, FL, USA, Nov. 2024, pp. 18584-18600, doi: 10.18653/v1/2024.emnlp-main.1034.

---

## 6. Verification log

Independent fact-check carried out on 11 Oct 2026. Each reference was checked against a primary record fetched directly: Crossref DOI metadata (all 11 DOIs), the arXiv API and full-text HTML, OpenReview, the USENIX, NeurIPS, ICLR and ACL Anthology pages, the NVD REST API, and the original NIST, OWASP, Invariant Labs, Embrace The Red and Simon Willison pages. The AAAI OJS page for [26] returned HTTP 503, so [26] was confirmed through Crossref, whose record points to that page. Authors, titles, venues, years, pages and DOIs matched for all entries except the ones changed below.

**Bibliographic corrections**
- [18] Zou *et al.*: the paper is published in NeurIPS 2025 (Datasets and Benchmarks Track), pp. 88855-88891, doi: 10.52202/085713-2676 (Crossref; NeurIPS proceedings page; OpenReview). The citation was changed from the arXiv preprint to this version. The NeurIPS author list has 15 names and the arXiv one has 17; the entry notes which figures come from the arXiv version.
- [25] Hou *et al.*: now published in *ACM Trans. Softw. Eng. Methodol.*, vol. 35, no. 10, pp. 1-37, 2026, doi: 10.1145/3796519 (Crossref). The citation was updated. The note that arXiv v1 described a three-phase lifecycle was confirmed on the v1 abstract page.
- [30] OWASP: the 2025 edition of the list was released in November 2024 (OWASP announcement dated Nov. 17/19, 2024), so the reference date was changed from "2025" to "Nov. 2024".
- [20] NIST CAISI blog: the cited `caisi-research-blog` URL now returns HTTP 301 to `caissi-research-blog`, because NIST has since renamed the center CAISSI. The URL was updated and an access date was added. The author and blog name are kept as they were at publication; the page body still says "Center for AI Standards and Innovation (CAISI)".
- [24] Radosevich & Halloran: Crossref shows a later SPIE proceedings version (*Assurance and Security for AI-enabled Systems 2026*, doi: 10.1117/12.3097390) with a different author list (J. T. Halloran, B. Radosevich, G. Black). The arXiv preprint is still cited, because it is the version summarized, and the newer version is noted in the entry. The SPIE volume number was not confirmed, so it is not given.

**Content corrections**
- [12] AgentDojo: "PI detector roughly halved benign utility" was wrong. Table 5 of arXiv v3 shows benign utility falling from 69.0% to 41.5% (utility under attack falls from 50.0% to 21.1%), and the text now says so. Synthesis item 5 was fixed the same way. The limitation about tool filtering was marked "(our analysis)", but the AgentDojo authors make that point themselves (17% of test cases), so it is now attributed to them.
- [27] MSB: the entry said MSB "introduces" NRP. ASB [13] introduced Net Resilient Performance, and MSB adapts it, computing it under attack (MSB Sec. 5). [13], [27] and Section 4.3 were corrected.
- [6] Tensor Trust: the ICLR abstract describes the dataset as the *first* to contain both human-generated attacks and defenses, not the "largest". The text was corrected. The spotlight status was confirmed on OpenReview ("ICLR 2024 spotlight").
- [15] Adaptive attacks: the >50% ASR result holds on the 100-case InjecAgent subset (Vicuna-7B and Llama3-8B agents). On the 16-case AgentDojo appendix check, the gains were smaller. This is now stated.
- [10] Instruction hierarchy: [16] does not attack the instruction hierarchy itself; it attacks related training-based defenses (StruQ, MetaSecAlign), and the limitation now says so. OpenReview lists [10] only as "Submitted to ICLR 2025", so it stays a preprint.
- [19]/[20]: according to NIST, CAISI, the UK AISI and frontier labs partnered with Gray Swan on the *analysis and paper*, so the text no longer says they ran the competition.
- [1], [4], [5], [21]: wording was tightened to match the sources. Willison (2022) says he has "no idea how feasible" separate channels are, and the 2023 update calls them extremely difficult. HouYi's exploratory study reports that existing attacks had limited success in practice, and the unverified explanation was dropped. Rehberger says OpenAI's criteria require confirmation but review did not appear to enforce it. The trifecta post's advice to developers and to end users is now separated.
- [28]: "peer-reviewed symposium paper" was changed to "published in the AAAI Symposium Series proceedings", because the review process could not be confirmed. [29]: CWE-74 is now attributed to Microsoft, the CNA, as the NVD record shows.
- Statements that no Arabic benchmark or detector exists, and that all benchmarks are English-only, cannot be proven from the cited sources. G7, Section 4.1 item 8, Section 4.3 and the [31] relevance note now say "we found none in the literature reviewed". The [11] "first benchmark" claim is now attributed to the authors. The table entry "agent hijacking in [17]-[20]" was narrowed to [17], [20], the sources that use that term.

**Confirmed without change (main checks)**
- [2]: OpenReview venue is NeurIPS 2022 ML Safety Workshop (MLSW).
- [3], [9], [11], [14], [15], [26], [28], [31]: pages and DOIs match Crossref.
- [8]: USENIX BibTeX gives pp. 1831-1847, Aug. 2024. The finding that larger LLMs are more vulnerable is in Sec. 5.
- [13]: OpenReview shows "ICLR 2025 Poster". [27]: OpenReview shows "ICLR 2026 Poster".
- [16]: 14 authors and 12 defenses. OpenReview shows it only as a submission to ICLR 2026, so it stays a preprint.
- [17]: NIST page dates (Jan. 17, 2025, updated Dec. 19, 2025) and the 11%→81% and 57%→80% figures.
- [19]: 31 authors; 272k attempts; ASR 0.5% (Claude Opus 4.5) to 8.5% (Gemini 2.5 Pro).
- [22], [23]: author bylines and dates on the Invariant pages.
- [5]: Embrace The Red is Johann Rehberger's blog. Willison's Aug. 2025 post links Rehberger's work to embracethered.com.
- [29]: NVD gives Microsoft 9.3 and NVD 7.5 (CVSS 3.1), published Jun. 11, 2025.
- WASP: 86% intermediate; 0-17% end-to-end (Sec. 1) and up to 16% (Sec. 4).
- InjecAgent: the hacking prompt text and the 24%→47% increase.
- MCPTox: 1,312 cases in arXiv v1 and 1,348 in the AAAI version.
