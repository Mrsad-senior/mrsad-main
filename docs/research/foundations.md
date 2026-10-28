# Foundational Computer-Science and Engineering Methods Behind Mirsad

*Research track: foundations. Mirsad (مرصاد) IS499 Senior Project, Prince Sultan University, 2026-2027. Compiled 11 October 2026.*

## Introduction

Mirsad is a runtime firewall placed between an LLM agent and its tools (MCP servers and OpenAI-style function calls). Most of its mechanisms are not new. They reuse decades-old results from computer security, human-computer interaction and software engineering, and apply them to a new kind of software: an agent that a planner model drives with natural-language input. This track collects the primary sources for those mechanisms so the team can cite them precisely and know where each one stops applying. The sources fall into ten groups. (1) Information-flow control and taint analysis underpin Mirsad's tracking of untrusted content to external sinks. (2) Reference-monitor design principles justify routing every tool call through a single gateway. (3) Hash-chained and MAC-protected logging is the basis of the tamper-evident audit trail. (4) Attribute-based policy languages (XACML, OPA/Rego) inform the declarative per-tool and per-parameter policy format. (5) Threat modeling (Shostack, STRIDE) structures the security analysis. (6) The ReAct and Toolformer papers describe the tool-using agent pattern Mirsad protects. (7) Human-AI interaction and automation research guides the human-in-the-loop approval design, and the Keystroke-Level Model gives a way to estimate how much effort an approval costs. (8) Datasheets and model cards set the documentation norms for the detector and its dataset. (9) Web-platform and IETF specifications (WCAG 2.2, Web App Manifest, Service Workers, JWT, scrypt) cover the mobile approval app and its authentication. (10) ISO/IEC/IEEE standards and the Scrum Guide govern how the project specifies, tests and manages its work.

**How the sources were checked.** Each reference was checked against a reachable authoritative record: the Crossref DOI metadata for ACM, IEEE and Springer papers; the NDSS, USENIX, ICLR and NeurIPS proceedings pages; arXiv; the RFC Editor; W3C TR pages and their publication histories; OASIS; the IEC webstore entries for the ISO/IEC/IEEE standards; Microsoft Learn; the Wiley product page; and scrumguides.org. Where a detail could not be confirmed, such as the proceedings page range for the USENIX Security 2009 paper, it is left out instead of guessed. The W3C living specifications are cited at the version current on the access date. A second, independent verification pass was made on 11 October 2026; its results and corrections are listed in the Verification log at the end.

---

## A. Information-flow control and taint analysis

### [1] Denning (1976): lattice model of secure information flow

**Reference.** D. E. Denning, "A lattice model of secure information flow," *Commun. ACM*, vol. 19, no. 5, pp. 236–243, May 1976, doi: 10.1145/360051.360056.

**Summary.** Denning gives a mathematical model of secure information flow. Every storage object and process is bound to a security class, and the classes, together with a "can-flow-to" relation and a class-combining (join) operator, form a lattice. A flow from one object to another is secure only if it respects the ordering of their classes. The lattice structure lets the security requirements of many existing systems be written compactly and classified. The model also leads directly to automatic mechanisms that certify a program's flows as secure. It covers both explicit flows (assignments) and implicit flows that pass through control structure.

**Strengths and limitations.** The model is general, elegant and still the vocabulary of the field. Combining labels with a join keeps the analysis compositional. It assumes precise, program-level knowledge of every flow, and labels only move upward. Without an explicit downgrading step, data therefore tends to become more and more restricted (label creep).

**Relevance to Mirsad.** Mirsad's taint labels (for example *trusted user input* versus *untrusted tool output from the web*) are a two-point or small lattice in Denning's sense. Joining the labels of everything in the agent's context decides the label of a proposed tool argument. The label-creep problem is exactly why Mirsad needs a controlled release path, namely human approval.

### [2] Sabelfeld and Myers (2003): language-based information-flow security

**Reference.** A. Sabelfeld and A. C. Myers, "Language-based information-flow security," *IEEE J. Sel. Areas Commun.*, vol. 21, no. 1, pp. 5–19, Jan. 2003, doi: 10.1109/JSAC.2002.806121.

**Summary.** This survey argues that conventional mechanisms such as access control and encryption decide who may *access* data but do not guarantee where the data *flows* afterwards. Its central policy is noninterference: an observer must not be able to infer secret inputs from public outputs. It reviews about thirty years of research, focusing on static enforcement through security-type systems. It then organizes recent work into four trends: more expressive languages, concurrency, covert channels, and refined security policies, including declassification (downgrading) of information. It ends with open challenges for making the techniques practical.

**Strengths and limitations.** It is the standard map of the area and a precise reference for terms such as noninterference, implicit flow and covert channel. Its techniques assume a program whose source can be analysed and whose semantics are fixed. An LLM agent has neither: the "program" is a stochastic model steered by text.

**Relevance to Mirsad.** It explains why Mirsad cannot claim noninterference. Once untrusted text enters an LLM's context, the model may let it influence any output, so Mirsad must use a conservative, coarse-grained approximation at the tool boundary instead of a proof. Its discussion of declassification supports Mirsad's design choice to treat human approval as an explicit, logged declassification event.

### [3] Newsome and Song (2005): dynamic taint analysis (TaintCheck)

**Reference.** J. Newsome and D. Song, "Dynamic taint analysis for automatic detection, analysis, and signature generation of exploits on commodity software," in *Proc. 12th Annu. Netw. Distrib. Syst. Secur. Symp. (NDSS)*, San Diego, CA, USA, Feb. 2005. [Online]. Available: https://www.ndss-symposium.org/ndss2005/dynamic-taint-analysis-automatic-detection-analysis-and-signaturegeneration-exploits-commodity/

**Summary.** The paper labels all data arriving from untrusted sources (e.g., the network) as *tainted* and tracks how that label spreads while the program runs. An alarm is raised when tainted data reaches a sensitive use, such as a jump target or a format string. The prototype, TaintCheck, rewrites binaries at run time, so it needs no source code or recompilation and works on commodity software. The authors report that it detected most types of overwrite exploits with no false positives on the programs they tested. They also show how the recorded taint trace can help generate exploit signatures.

**Strengths and limitations.** It established the *source → propagation → sink* vocabulary used throughout later taint systems, and it showed that dynamic tracking works on unmodified software. Its byte-level propagation and fixed sink set suit memory-corruption attacks. It cannot be applied directly to semantic attacks in which the "payload" is persuasive natural language.

**Relevance to Mirsad.** Mirsad adapts the same three-part model. *Sources* are tool results from untrusted origins (web pages, emails, files). *Propagation* is conservative, applied at message or session granularity through the LLM. *Sinks* are tools with external side effects (sending email, HTTP POST, file writes). When tainted data reaches a sink, the result is a policy decision (block, require approval) instead of a crash. The paper is the direct ancestor of Mirsad's taint module.

---

## B. Security design principles

### [4] Saltzer and Schroeder (1975): the protection of information in computer systems

**Reference.** J. H. Saltzer and M. D. Schroeder, "The protection of information in computer systems," *Proc. IEEE*, vol. 63, no. 9, pp. 1278–1308, Sep. 1975, doi: 10.1109/PROC.1975.9939.

**Summary.** This tutorial paper surveys mechanisms for protecting stored information. It is best known for its eight design principles: economy of mechanism, fail-safe defaults, complete mediation, open design, separation of privilege, least privilege, least common mechanism and psychological acceptability. It also explains capability-based and access-control-list protection, and how authentication relates to authorization. The principles are framed as engineering guidance rather than formal requirements.

**Strengths and limitations.** The principles have lasted for fifty years and are still cited in security standards. They are qualitative and sometimes pull against each other: complete mediation and psychological acceptability, for example. Applying them takes judgment.

**Relevance to Mirsad.** Mirsad's architecture applies *complete mediation* (every tool call passes the gateway), *fail-safe defaults* (unknown tools or parameters are denied or escalated), *least privilege* (per-tool, per-parameter allow-lists) and *separation of privilege* (a human approver for high-risk calls). *Psychological acceptability* is the design constraint behind keeping approvals rare and fast (see [15]–[17]).

---

## C. Tamper-evident logging and message authentication

### [5] Haber and Stornetta (1991): how to time-stamp a digital document

**Reference.** S. Haber and W. S. Stornetta, "How to time-stamp a digital document," *J. Cryptol.*, vol. 3, no. 2, pp. 99–111, 1991, doi: 10.1007/BF00196791.

**Summary.** The paper asks how to certify when a digital document was created or last changed without having to trust a single time-stamping service completely. One of its proposals links each time-stamp certificate to the one before it by including a cryptographic hash of the previous certificate. Back-dating or forward-dating a document then requires rewriting the whole chain after it. A second proposal spreads trust across randomly chosen witnesses. The hash-linking idea later became the basis of many tamper-evident and append-only data structures.

**Strengths and limitations.** It shows how hash linking turns local integrity checks into evidence about ordering for the whole history. Verifying an old entry requires walking the chain. The scheme also relies on parties other than the time-stamping service (the other clients, who hold neighbouring certificates) keeping copies of the links; a party that controlled every copy could rewrite the history.

**Relevance to Mirsad.** Mirsad's audit log stores in each event the hash of the previous event. This is the linking technique from this paper. Mirsad's exportable anchor of the newest hash, kept outside the gateway, plays the same role as the paper's reliance on copies held outside the time-stamping service.

### [6] Schneier and Kelsey (1999): secure audit logs to support computer forensics

**Reference.** B. Schneier and J. Kelsey, "Secure audit logs to support computer forensics," *ACM Trans. Inf. Syst. Secur.*, vol. 2, no. 2, pp. 159–176, May 1999, doi: 10.1145/317087.317089.

**Summary.** The authors consider an untrusted logging machine that only occasionally contacts a trusted machine. They aim to make every log entry written *before* a compromise unreadable to the attacker and impossible to alter or delete without detection. The scheme evolves the per-entry keys one-way (each key derived by hashing the previous one), encrypts the entries, chains them with hashes, and authenticates the chain with MACs. As a result, an attacker who captures the current key learns nothing that would let them forge earlier entries. They state the limits of any such scheme plainly: entries written after compromise cannot be protected, and cryptography can detect deletion but not prevent it.

**Strengths and limitations.** The forward-integrity idea and the clear statement of what is and is not achievable are its lasting contributions. The scheme relies on a trusted party for verification. Verification is linear in log length, and truncating the end of the log can only be detected once the logger next contacts the trusted machine.

**Relevance to Mirsad.** Mirsad's audit log (an HMAC-SHA256 chain over `prev_hash` plus a canonical JSON event body) follows this design closely, and its code comments acknowledge the same limits: truncation, or a rewrite by whoever holds the key, can only be detected against an external anchor. Key evolution would be a natural future strengthening, so that compromising the gateway's current key does not expose past entries.

### [7] Crosby and Wallach (2009): efficient data structures for tamper-evident logging

**Reference.** S. A. Crosby and D. S. Wallach, "Efficient data structures for tamper-evident logging," in *Proc. 18th USENIX Secur. Symp.*, Montreal, QC, Canada, Aug. 2009. [Online]. Available: https://www.usenix.org/conference/usenixsecurity09/technical-sessions/presentation/efficient-data-structures-tamper-evident

**Summary.** The paper models an untrusted logger, clients that submit events, and auditors who challenge the logger. Tamper evidence is defined in terms of two proofs: that a particular event is still in the log (membership), and that the current log extends an earlier version (consistency). The authors replace the linear hash chain with a Merkle-tree-based *history tree*, which gives logarithmic-size proofs. In their example, a 3 KB proof replaces the roughly 800 MB trace a hash chain would need for an 80-million-event log. They also support authenticated search and agreed-upon deletion of old events, and report a prototype logging 1,750 events per second on one core (more when signatures are offloaded).

**Strengths and limitations.** It gives a precise auditing semantics and large efficiency gains. The design is more complex than a hash chain, and it still needs auditors to gossip or keep earlier commitments in order to detect forks.

**Relevance to Mirsad.** It supplies both the auditing vocabulary (membership versus consistency proofs) for Mirsad's verification report and a clear upgrade path. If Mirsad's audit volume grows, or if external parties need to audit selected events without downloading the whole log, a history tree could replace the linear chain.

### [8] Krawczyk, Bellare and Canetti (1997): HMAC, RFC 2104

**Reference.** H. Krawczyk, M. Bellare, and R. Canetti, "HMAC: Keyed-hashing for message authentication," RFC 2104, Feb. 1997, doi: 10.17487/RFC2104.

**Summary.** This informational RFC specifies HMAC, a message authentication code built from any iterated cryptographic hash function and a shared secret key. The hash is applied twice, with the key combined with an inner and an outer padding constant. This design keeps the hash function as a replaceable component. The document covers key length and handling, optional truncation of the output, security considerations, sample code and test vectors. It was later updated by RFC 6151, which revised the security considerations for MD5-based variants.

**Strengths and limitations.** HMAC is simple and standardized everywhere. The RFC's security argument needs only a weak, secret-key form of collision resistance (finding collisions when the initial value is secret and random), which is much harder to break than ordinary collision resistance. Because it is symmetric, anyone who can verify the log can also forge entries. It provides integrity, not non-repudiation.

**Relevance to Mirsad.** HMAC-SHA256 is the primitive that links Mirsad's audit chain, so recomputing the chain requires the secret key. Mirsad derives a separate audit HMAC key from the application secret, keeping it apart from the JWT signing key ([23]). The symmetric-key limitation is a known threat-model assumption to state in the report.

---

## D. Declarative policy languages

### [9] OASIS (2013): eXtensible Access Control Markup Language (XACML) 3.0

**Reference.** E. Rissanen, Ed., "eXtensible Access Control Markup Language (XACML) Version 3.0," OASIS Standard, Jan. 22, 2013. [Online]. Available: https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html

**Summary.** XACML 3.0 is an attribute-based access-control policy language and a request/response protocol. It defines a reference architecture. A Policy Enforcement Point (PEP) intercepts requests, a Policy Decision Point (PDP) evaluates them, a Policy Information Point (PIP) supplies attributes, and a Policy Administration Point (PAP) manages policies. Policies are built from rules (target, condition, Permit/Deny effect) grouped into policies and policy sets. Combining algorithms such as *deny-overrides* and *first-applicable* resolve conflicts, and a decision can carry *obligations* that the PEP must carry out and *advice* it may ignore. A later edition, XACML 3.0 Plus Errata 01 (OASIS Standard incorporating Approved Errata, 12 July 2017), is the current "latest version."

**Strengths and limitations.** XACML is the reference vocabulary for separating policy decisions from enforcement and for resolving conflicts in a well-defined way. Its XML syntax is verbose and hard for people to write, which is one reason simpler policy-as-code languages have largely replaced it in practice.

**Relevance to Mirsad.** Mirsad's gateway acts as the PEP and its policy engine as the PDP. Taint labels and detector scores play the role of PIP attributes. "Require human approval" behaves like an obligation. Precedence among matching rules, such as a deny on a parameter pattern overriding a tool-level allow, should be documented using XACML's combining-algorithm terminology.

### [10] Open Policy Agent: the Rego policy language

**Reference.** Open Policy Agent, "Policy language," *OPA Documentation*. [Online]. Available: https://www.openpolicyagent.org/docs/policy-language (accessed Oct. 11, 2026).

**Summary.** Open Policy Agent (OPA) is a general-purpose policy engine. A service sends OPA a structured JSON query, OPA evaluates it against policies written in Rego, and the service enforces whatever decision comes back. Rego is a declarative language inspired by Datalog and extended to handle nested JSON-like documents. Policies are built from rules, comprehensions, functions and packages. The documentation describes decisions as arbitrary structured values computed from request `input` and pre-loaded `data`, and the project offers testing and type-checking tools. OPA graduated within the Cloud Native Computing Foundation in February 2021.

**Strengths and limitations.** Policy-as-code makes policies testable, version-controlled and reviewable. The declarative style helps auditing. Rego's Datalog semantics take time to learn, and running OPA adds an extra dependency and a network or library hop.

**Relevance to Mirsad.** Mirsad's YAML per-tool/per-parameter policies follow the same pattern: decoupled decisions, declarative rules, and content-addressed policy versions recorded in the audit log. OPA/Rego is the main baseline to compare against when justifying a domain-specific policy format. A future Rego export could let organizations reuse their existing OPA toolchains.

---

## E. Threat modeling

### [11] Shostack (2014): Threat Modeling: Designing for Security

**Reference.** A. Shostack, *Threat Modeling: Designing for Security*. Indianapolis, IN, USA: John Wiley & Sons, 2014, ISBN: 978-1-118-80999-0.

**Summary.** Shostack, who was responsible for Security Development Lifecycle threat modeling at Microsoft, presents threat modeling as a practical engineering activity organized around four questions. In the 2014 wording these are: what are you building, what can go wrong once it is built, what should you do about those things, and did you do a decent job of analysis? (Later material by Shostack rewords them, e.g. "did we do a good job?") The book compares asset-centric, attacker-centric and software-centric approaches. It uses data-flow diagrams with trust boundaries and teaches STRIDE (including a STRIDE-per-element table, Appendix B), attack trees and the *Elevation of Privilege* card game (Appendix D). Later parts cover managing and validating mitigations and threat modeling for specific technologies.

**Strengths and limitations.** It is practical, method-agnostic and suitable for students. It predates LLM agents, so threats such as prompt injection through tool outputs must be mapped onto its categories by the team. A second edition subtitled *Designing for Security in an AI World* is announced for January 2027; check it before the final report.

**Relevance to Mirsad.** The four-question framework and data-flow-diagram method structure the threat-model chapter of the report. Placing trust boundaries between the user, the LLM provider, the Mirsad gateway, MCP servers and external web content shows exactly where the taint sources and sinks lie.

### [12] Microsoft: STRIDE threat categories

**Reference.** Microsoft, "Threats - Microsoft Threat Modeling Tool - Azure," *Microsoft Learn*. [Online]. Available: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats (accessed Oct. 11, 2026).

**Summary.** Microsoft's documentation for its Threat Modeling Tool defines the six STRIDE categories: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service and Elevation of privilege. Most categories come with an example of how they show up in real systems, and the page defines non-repudiation as a system's ability to counter repudiation threats. It presents the tool as a core element of the Microsoft Security Development Lifecycle (SDL), designed so that non-security experts can create and analyse threat models. The page does not state which security property each category violates. That mapping (authentication, integrity, non-repudiation, confidentiality, availability and authorization respectively) is given in Shostack's STRIDE-per-element table [11, App. B] and should be cited from there.

**Strengths and limitations.** STRIDE is quick to apply and gives a checklist the whole team can use. Its categories classify threats but do not rank them by likelihood or impact, so it needs to be combined with a risk-rating method.

**Relevance to Mirsad.** Indirect prompt injection maps onto several STRIDE categories. It is *Elevation of privilege*, because untrusted content takes over the agent's authority. It leads to *Information disclosure* through exfiltration via a sink, and to *Tampering* with tool arguments. Mirsad's audit chain directly addresses *Repudiation*. Applying STRIDE to each element of the data-flow diagram (STRIDE-per-element, [11]) should drive the selection of test scenarios.

---

## F. Tool-using LLM agents

### [13] Yao et al. (2023): ReAct

**Reference.** S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao, "ReAct: Synergizing reasoning and acting in language models," in *Proc. 11th Int. Conf. Learn. Represent. (ICLR)*, Kigali, Rwanda, 2023. [Online]. Available: https://arxiv.org/abs/2210.03629

**Summary.** ReAct prompts a language model to alternate between free-text reasoning traces and concrete actions (e.g., search or lookup calls). The observations returned by those actions feed back into the next reasoning step. On HotpotQA and FEVER, calling a simple Wikipedia API reduced the hallucination and error propagation seen with chain-of-thought reasoning alone. On the ALFWorld and WebShop decision-making benchmarks, ReAct with one or two in-context examples beat imitation- and reinforcement-learning baselines by 34 and 10 absolute percentage points of success rate. The interleaved traces also make the agent's behaviour easier to interpret.

**Strengths and limitations.** It is simple, general and became the template for most agent frameworks. It assumes tool observations are honest. Nothing in the loop separates *data* returned by a tool from *instructions*, which is the root cause of indirect prompt injection.

**Relevance to Mirsad.** ReAct defines the reason → act → observe loop that Mirsad mediates. Every *act* step is a tool call Mirsad checks against policy, and every *observe* step is a possible taint source. The paper is the standard citation for the agent architecture Mirsad protects.

### [14] Schick et al. (2023): Toolformer

**Reference.** T. Schick, J. Dwivedi-Yu, R. Dessì, R. Raileanu, M. Lomeli, E. Hambro, L. Zettlemoyer, N. Cancedda, and T. Scialom, "Toolformer: Language models can teach themselves to use tools," in *Adv. Neural Inf. Process. Syst. (NeurIPS)*, vol. 36, 2023, pp. 68539–68551, doi: 10.52202/075280-2997.

**Summary.** Toolformer trains a language model to decide on its own which external APIs to call, when to call them, what arguments to pass and how to use the results. Training data is produced in a self-supervised way. The model proposes candidate API calls inside ordinary text, and only those calls whose results make the following tokens easier to predict are kept for fine-tuning. The tools include a calculator, a question-answering system, a search engine, a translation system and a calendar. The authors report clearly better zero-shot performance on several downstream tasks, often competitive with much larger models, without loss of core language-modelling ability.

**Strengths and limitations.** It shows that tool use can be learned with few human annotations. Its tools are read-only and benign, and the paper does not consider adversarial tool outputs or tools with side effects.

**Relevance to Mirsad.** Together with ReAct, it is evidence that tool calling is becoming a native model capability rather than a prompt trick. Defences therefore have to sit at the tool interface, outside the model, which is where Mirsad sits. Its lack of a threat model for tool outputs is a gap Mirsad fills.

---

## G. Human-AI interaction, automation and interaction cost

### [15] Amershi et al. (2019): guidelines for human-AI interaction

**Reference.** S. Amershi, D. Weld, M. Vorvoreanu, A. Fourney, B. Nushi, P. Collisson, J. Suh, S. Iqbal, P. N. Bennett, K. Inkpen, J. Teevan, R. Kikin-Gil, and E. Horvitz, "Guidelines for human-AI interaction," in *Proc. CHI Conf. Human Factors Comput. Syst. (CHI '19)*, Glasgow, U.K., 2019, pp. 1–13, doi: 10.1145/3290605.3300233.

**Summary.** The authors synthesize more than two decades of guidance into 18 generally applicable design guidelines for AI-infused systems. The guidelines are organized by when they apply: at initial interaction, during interaction, when the AI is wrong, and over time. Examples include making clear what the system can do and how well, explaining why it did something, supporting efficient correction and dismissal, and scoping its services when it is uncertain. The guidelines were refined over several rounds of evaluation, including a study in which 49 design practitioners tested them against 20 popular AI products. The paper received a CHI 2019 honorable mention.

**Strengths and limitations.** The guidelines are empirically validated, concrete and widely adopted (Microsoft's HAX Toolkit). They target consumer AI features, not security-critical approval workflows, and they say little about adversarial settings or alert fatigue.

**Relevance to Mirsad.** These guidelines should drive the mobile approval screen. The screen should explain *why* a call was flagged (which policy rule, which tainted source, which detector cue). It should make approve and deny efficient, show what each decision will cause, and learn over time by suggesting policy updates for calls that are approved repeatedly. They give the report a validated heuristic checklist for its usability evaluation.

### [16] Parasuraman, Sheridan and Wickens (2000): types and levels of human interaction with automation

**Reference.** R. Parasuraman, T. B. Sheridan, and C. D. Wickens, "A model for types and levels of human interaction with automation," *IEEE Trans. Syst., Man, Cybern. A, Syst. Humans*, vol. 30, no. 3, pp. 286–297, May 2000, doi: 10.1109/3468.844354.

**Summary.** The paper argues that automation is not all-or-nothing. It can be applied to four stages of information processing (information acquisition, information analysis, decision and action selection, and action implementation), each at a different level, ranging from fully manual to fully autonomous. It proposes choosing those levels using primary criteria (human performance effects such as mental workload, situation awareness, complacency and skill degradation) and secondary criteria (automation reliability and the costs of decision and action consequences). The model is meant as a design framework rather than a prescription.

**Strengths and limitations.** It offers a clear vocabulary for *how much* to automate and *where*. It predates machine-learning systems whose reliability varies from one input to the next, so the level may need to change per request.

**Relevance to Mirsad.** Mirsad automates information analysis (taint, detector) and decision selection (policy). The level of automation for action implementation varies with risk: auto-allow, auto-block, or a human consent step. The paper's warnings about complacency and workload justify approving only high-risk calls instead of every call, and they suggest measuring approver accuracy as well as speed.

### [17] Card, Moran and Newell (1980): the Keystroke-Level Model

**Reference.** S. K. Card, T. P. Moran, and A. Newell, "The keystroke-level model for user performance time with interactive systems," *Commun. ACM*, vol. 23, no. 7, pp. 396–410, Jul. 1980, doi: 10.1145/358886.358895.

**Summary.** The Keystroke-Level Model (KLM) predicts how long an expert user takes to complete a routine task, without error, on a given interface. The method breaks the task into primitive operators (keystrokes, pointing, homing the hands, drawing, mental preparation and system response time) and adds up a standard time for each. Heuristic rules specify where mental-preparation operators go. The paper estimates the mental-preparation operator M at 1.35 s on average, pointing P at 1.10 s and homing H at 0.40 s, with keystroke times from 0.08 s to 1.20 s depending on typing skill. Tested against data from ten different systems, the model's prediction error for individual tasks was 21 percent. It lets designers compare alternative interfaces analytically before building them.

**Strengths and limitations.** KLM is cheap, repeatable and needs no participants, which suits early design. It models only error-free expert performance. It ignores learning, errors and fatigue, and its operator times were calibrated for desktop keyboards and mice, not touchscreens.

**Relevance to Mirsad.** KLM gives an analytical estimate of the *cost per approval* on the mobile app: open the notification, read the summary, tap approve or deny. That estimate can be compared across design alternatives and against measured times in user tests. Because approval overhead is the main usability cost of human-in-the-loop security, this quantification is central to Mirsad's evaluation. Touch-screen adaptations of the operator values should be noted as a limitation.

---

## H. Documentation for datasets and models

### [18] Gebru et al. (2021): datasheets for datasets

**Reference.** T. Gebru, J. Morgenstern, B. Vecchione, J. W. Vaughan, H. Wallach, H. Daumé III, and K. Crawford, "Datasheets for datasets," *Commun. ACM*, vol. 64, no. 12, pp. 86–92, Dec. 2021, doi: 10.1145/3458723.

**Summary.** The paper borrows the idea of electronic-component datasheets and proposes that every machine-learning dataset come with a datasheet. The datasheet documents the dataset's motivation, composition, collection process, preprocessing and labelling, recommended uses, distribution and maintenance. It is structured as a set of questions for dataset creators to answer, meant to prompt reflection as well as disclosure. The goals are better communication between dataset creators and consumers and more transparency and accountability. The CACM article is the published version of a preprint first posted to arXiv in 2018.

**Strengths and limitations.** The question list is concrete and reusable, and it has been widely adopted. It is voluntary and qualitative, and filling it in thoroughly takes real effort.

**Relevance to Mirsad.** Mirsad's Arabic/English injection benchmark and detector training data should ship with a datasheet. It should record the provenance of attack and benign samples, the dialect and code-switching coverage, labelling procedure and agreement, overlap with public benchmarks, and the licensing of any reused corpora.

### [19] Mitchell et al. (2019): model cards for model reporting

**Reference.** M. Mitchell, S. Wu, A. Zaldivar, P. Barnes, L. Vasserman, B. Hutchinson, E. Spitzer, I. D. Raji, and T. Gebru, "Model cards for model reporting," in *Proc. Conf. Fairness, Accountability, Transparency (FAT\* '19)*, Atlanta, GA, USA, 2019, pp. 220–229, doi: 10.1145/3287560.3287596.

**Summary.** The paper proposes *model cards*: short documents released with trained models. A model card reports the model's details, intended use, relevant factors (e.g., demographic or environmental groups), metrics, evaluation and training data, quantitative results broken down by factor, ethical considerations, and caveats. The authors show worked examples, including an image-based smile detector and a text toxicity classifier, to show how disaggregated evaluation can reveal performance gaps between groups that a single aggregate metric hides.

**Strengths and limitations.** It is a lightweight, widely adopted template that encourages evaluation broken down by group. Model cards are self-reported and not audited, and their quality depends on the evaluation data available.

**Relevance to Mirsad.** The injection detector needs a model card. It should report results separately for Arabic (Modern Standard and dialects) and English, and for direct versus indirect and obfuscated attacks. It should state false-positive rates on benign tool outputs, the intended deployment (a pre-filter that informs the policy, not a sole defence), and known evasion limits.

---

## I. Web platform and authentication building blocks

### [20] W3C (2023): Web Content Accessibility Guidelines (WCAG) 2.2

**Reference.** A. Campbell, C. Adams, R. B. Montgomery, M. Cooper, and A. Kirkpatrick, Eds., "Web Content Accessibility Guidelines (WCAG) 2.2," W3C Recommendation, Oct. 5, 2023 (updated Dec. 12, 2024). [Online]. Available: https://www.w3.org/TR/WCAG22/

**Summary.** WCAG 2.2 defines testable success criteria under four principles: content must be perceivable, operable, understandable and robust. Conformance has three levels (A, AA, AAA). Compared with WCAG 2.1 it adds nine success criteria, including focus not obscured, alternatives to dragging movements, a minimum target size, accessible authentication, avoiding redundant entry and consistent help. It also removes the obsolete 4.1.1 Parsing criterion. Content that conforms to 2.2 also conforms to 2.0 and 2.1, although policies that still require 2.0 or 2.1 may need 4.1.1 to be tested and reported separately.

**Strengths and limitations.** It is the internationally recognized accessibility baseline, and its criteria can be tested. It is technology-neutral, so mobile-specific and right-to-left concerns are handled indirectly through general criteria, and some criteria require human judgement to evaluate.

**Relevance to Mirsad.** The approval app should target WCAG 2.2 Level AA. The most relevant new criteria are *Target Size (Minimum)* for the approve and deny buttons, *Accessible Authentication* for login, and *Focus Not Obscured*. Bilingual Arabic/English content needs correct language and direction markup so assistive technologies read it properly.

### [21] W3C: Web Application Manifest

**Reference.** M. Cáceres, D. Murphy, and C. Liebel, Eds., "Web Application Manifest," W3C Working Draft, Oct. 9, 2026. [Online]. Available: https://www.w3.org/TR/appmanifest/

**Summary.** The specification defines a JSON manifest that centralizes a web application's metadata. It includes full and short names, a set of icons at different sizes, a preferred start URL, a display mode (e.g., standalone or fullscreen), a navigation scope, orientation, theme and background colours, shortcuts, and language and text direction for localized values. Browsers and operating systems use it to install a web app and present it like a native app. The document is a living Working Draft maintained by the W3C Web Applications Working Group.

**Strengths and limitations.** It is simple, widely supported, and lets one web codebase be installed on both Android and iOS. Some members are advisory (the browser may ignore `start_url`), and support varies between engines.

**Relevance to Mirsad.** Mirsad's approval page links a web manifest, so approvers can install it to the home screen as a Progressive Web App without app-store distribution. The manifest's `dir` and `lang` members are relevant for the bilingual interface.

### [22] W3C: Service Workers

**Reference.** M. Chintala and Y. Yanagisawa, Eds., "Service Workers Nightly," W3C Candidate Recommendation Draft, Sep. 17, 2026. [Online]. Available: https://www.w3.org/TR/service-workers/

**Summary.** A service worker is an event-driven web worker registered for an origin and URL scope. It can intercept the network requests of the pages it controls through a `fetch` event, answer them from a programmable cache, and receive events such as push messages after the originating page has closed. The browser may stop a service worker when idle, so it must not keep state in memory. Its interfaces are available only in secure contexts (HTTPS). The specification has evolved through many Candidate Recommendation Drafts since the 2019 Candidate Recommendation Snapshot.

**Strengths and limitations.** Service workers enable offline use and background push, which are the defining capabilities of a PWA. They also add a persistent component that intercepts requests, so a misconfigured service worker could serve stale security decisions from its cache.

**Relevance to Mirsad.** Service workers make push notifications for pending approvals possible on the mobile app. Mirsad's security headers restrict `worker-src` to the same origin. For security, approval and decision API responses must never be served from the service-worker cache, which matches the `no-store` policy on API responses.

### [23] Jones, Bradley and Sakimura (2015): JSON Web Token, RFC 7519

**Reference.** M. Jones, J. Bradley, and N. Sakimura, "JSON Web Token (JWT)," RFC 7519, May 2015, doi: 10.17487/RFC7519.

**Summary.** RFC 7519 defines JWT, a compact, URL-safe way to represent claims transferred between two parties as a JSON object. The object is carried inside a JSON Web Signature (JWS) structure (signed or MACed) or a JSON Web Encryption (JWE) structure. It registers standard claims such as issuer, subject, audience, expiration, not-before, issued-at and JWT ID, and defines the processing rules for creating and validating tokens. It is a Proposed Standard, later updated by RFC 7797 and by the JWT Best Current Practices in RFC 8725.

**Strengths and limitations.** It is stateless, compact and supported by libraries in every language. Its flexibility has caused well-known pitfalls, such as algorithm confusion and accepting unsigned tokens, which RFC 8725 addresses. Revoking a token before it expires needs extra machinery.

**Relevance to Mirsad.** After a successful scrypt-verified login, Mirsad issues short-lived HS256 JWTs to authenticate approvers. The implementation should keep the algorithm pinned and validate `exp` (and `aud`/`iss` where used), following RFC 8725. Approval links should use short-lived, single-purpose tokens, and the JWT signing key must stay separate from the audit HMAC key (see [8]).

### [24] Percival and Josefsson (2016): the scrypt key-derivation function, RFC 7914

**Reference.** C. Percival and S. Josefsson, "The scrypt password-based key derivation function," RFC 7914, Aug. 2016, doi: 10.17487/RFC7914.

**Summary.** This informational RFC specifies scrypt, a password-based key-derivation function designed to need large amounts of memory. That makes brute-force attacks with custom-designed parallel hardware much more expensive than for purely CPU-bound functions such as PBKDF2. It defines the building blocks (the Salsa20/8 core, BlockMix and ROMix), the full algorithm and its cost parameters, an ASN.1 module for use in key formats such as PKCS #8, and test vectors. It also warns that very large parameters can be abused for memory-exhaustion denial of service.

**Strengths and limitations.** scrypt is a well-studied memory-hard function available in standard libraries (Python's `hashlib.scrypt`, for example). Choosing parameters is a trade-off between security and server load. Newer guidance often prefers Argon2, which this RFC predates.

**Relevance to Mirsad.** Mirsad's authentication module stores approver and administrator passwords as salted scrypt hashes in PHC string format, with cost parameters ln=14 (N = 2^14), r = 8 and p = 1, using Python's `hashlib.scrypt`. The report should cite this RFC for the algorithm and justify those parameters against login latency on the target hardware. The RFC's denial-of-service warning concerns attacker-supplied, unreasonably large parameters. Mirsad addresses it by rejecting stored hashes whose parsed cost parameters exceed fixed maxima, and its login throttle separately limits the memory load from repeated login attempts.

---

## J. Software-engineering process and quality standards

### [25] ISO/IEC/IEEE 29148:2018: requirements engineering

**Reference.** *Systems and Software Engineering — Life Cycle Processes — Requirements Engineering*, ISO/IEC/IEEE 29148:2018, Nov. 2018.

**Summary.** The second edition of this standard specifies the required processes for engineering the requirements of systems and software products, including services, across the life cycle. It explains how to apply the requirements-related processes of ISO/IEC/IEEE 15288 and 12207. It defines the information items those processes produce, such as stakeholder, system and software requirements specifications, their required content and recommended formats. It also describes the characteristics of well-formed individual requirements and requirement sets (e.g., necessary, unambiguous, verifiable, feasible, consistent). It applies whatever the project's size, method or complexity.

**Strengths and limitations.** It is the authoritative, internationally agreed basis for writing and organizing requirements. The full text is paid, and the standard is document-heavy, so agile teams usually tailor it rather than adopt it wholesale.

**Relevance to Mirsad.** The SRS chapter of the IS499 report should use this standard's structure and quality characteristics for requirements. Each functional requirement (e.g., "every tool call is evaluated against the active policy before forwarding") and each non-functional one (latency overhead, false-positive rate, approval time) should be verifiable and traceable to test cases under [26].

### [26] ISO/IEC/IEEE 29119: software testing (series)

**Reference.** *Software and Systems Engineering — Software Testing — Part 1: General Concepts*, ISO/IEC/IEEE 29119-1:2022, Feb. 2022. (Companion parts: *Part 2: Test Processes*, ISO/IEC/IEEE 29119-2:2021; *Part 3: Test Documentation*, ISO/IEC/IEEE 29119-3:2021; *Part 4: Test Techniques*, ISO/IEC/IEEE 29119-4:2021.)

**Summary.** The 29119 series is the international standard for software testing. Part 1 (2022) sets out general testing concepts and terms used across the series. Part 2 defines generic test processes at the organizational, management and dynamic-testing levels, usable with any life-cycle model. Part 3 provides templates and examples for test documentation (plans, specifications, completion reports). Part 4 catalogues test design techniques, such as equivalence partitioning, boundary-value analysis and others, and fits them into the Part 2 design-and-implementation process.

**Strengths and limitations.** It provides a shared vocabulary and documentation templates that examiners recognize. It is costly to obtain and has been criticized for being heavyweight. Lightweight tailoring is expected for student and agile projects.

**Relevance to Mirsad.** The testing chapter should use 29119-3 style test-case specifications and a test completion report. 29119-4 techniques suit the policy engine: equivalence partitioning and boundary values on parameter constraints, and decision-table testing on combinations of taint label, detector score and policy rule. Security attack suites and benchmark results then sit alongside the conventional tests.

### [27] Schwaber and Sutherland (2020): The Scrum Guide

**Reference.** K. Schwaber and J. Sutherland, "The 2020 Scrum Guide," Nov. 2020. [Online]. Available: https://scrumguides.org/scrum-guide.html

**Summary.** The Scrum Guide is the official, authors' definition of Scrum, a lightweight framework based on empiricism and lean thinking. Its three pillars are transparency, inspection and adaptation, and its values are commitment, focus, openness, respect and courage. The 2020 edition describes a single, self-managing Scrum Team (usually ten or fewer people) with three accountabilities: Developers, Product Owner and Scrum Master. It defines five events: the Sprint (one month or less), Sprint Planning, the Daily Scrum, the Sprint Review and the Sprint Retrospective. It defines three artifacts, each paired with a commitment: the Product Backlog with the Product Goal, the Sprint Backlog with the Sprint Goal, and the Increment with the Definition of Done. It is published under CC BY-SA 4.0.

**Strengths and limitations.** It is short, free and the canonical source for Scrum terminology. It deliberately leaves out practices (estimation, user stories, tooling), and a five-student team with academic deadlines will need to adapt event lengths and roles.

**Relevance to Mirsad.** The project-management chapter should cite the 2020 Guide for its sprint structure and Definition of Done. For a security product, the Definition of Done should include passing the policy and attack regression suites and verifying the audit chain. Requirements traceability ([25]) can link Product Backlog items to tests ([26]).

---

## Synthesis

### Themes

1. **Classic information-flow theory transfers to LLM agents at a coarse granularity.** Denning's lattice [1], Sabelfeld and Myers' noninterference [2] and Newsome and Song's source-propagation-sink model [3] give Mirsad its conceptual core. However, all three assume a program whose flows can be analysed, statically or dynamically, at the level of variables or bytes. An LLM is a black box that may mix any input into any output. Mirsad therefore applies taint at the boundary between messages and tool calls, and treats the model as fully propagating. This is sound but imprecise, and it makes label creep ([1]) and declassification ([2]) the central practical problems.

2. **Mediation, decision and enforcement are separate concerns.** Saltzer and Schroeder's complete mediation and fail-safe defaults [4], XACML's PEP/PDP/PIP architecture [9] and OPA's decoupled decision engine [10] all describe the same pattern Mirsad implements: a gateway that intercepts every call, a declarative policy engine that decides, and attribute providers (taint tracker, injection detector) that inform the decision. XACML's combining algorithms and obligations supply precise terms for documenting rule precedence and the "require approval" outcome.

3. **Tamper evidence is achievable, but only within stated limits.** Hash linking [5], forward-secure MAC-chained logs [6], logarithmic-proof history trees [7] and HMAC [8] form a direct lineage to Mirsad's HMAC-SHA256 audit chain. The literature is explicit that cryptography can *detect* but not *prevent* deletion, that entries written after a compromise cannot be protected, and that tail truncation requires an external anchor. Mirsad's design documentation already reflects these limits, and the sources supply the formal vocabulary for them (membership and consistency proofs, forward integrity).

4. **Human oversight is a designed component, not a fallback.** Amershi et al. [15] tell the team *what* an approval interface should communicate. Parasuraman et al. [16] explain *how much* to automate at each stage and warn about complacency and workload. The Keystroke-Level Model [17] measures *how much effort* each approval costs. Together they argue for approving rarely and explaining clearly, and for evaluating approval accuracy as well as speed.

5. **Agent capability research has no threat model for tool outputs.** ReAct [13] and Toolformer [14] established tool use as a core LLM capability but assume honest observations and mostly read-only tools. Threat-modeling methods [11], [12] give a systematic way to see that the observe step is a trust boundary crossing, which is the gap Mirsad's firewall closes.

6. **Accountability through documentation and process.** Datasheets [18] and model cards [19] set the transparency norms for Mirsad's bilingual detector and dataset. ISO/IEC/IEEE 29148 [25], 29119 [26] and the Scrum Guide [27] provide the traceable, verifiable engineering process an academic security project is judged on. WCAG 2.2 [20], the Web App Manifest [21], Service Workers [22], JWT [23] and scrypt [24] are the concrete, standard building blocks of a secure and accessible approval channel.

### Gaps in the foundations that Mirsad addresses

- **From program taint to agent taint.** No foundational IFC or taint source covers a nondeterministic language model as the propagation medium, or natural-language instructions as the "exploit." Mirsad contributes a practical, conservative taint discipline at the agent-tool boundary, with per-sink policy rather than per-instruction checks.
- **Declassification by a human, with an audit trail.** IFC theory treats declassification as a policy feature. Mirsad makes it an explicit, auditable human decision, recording who approved which tainted flow, under which policy version, in a tamper-evident log. This combines [2], [6] and [15] in a way none of them describes alone.
- **LLM-specific policy attributes.** XACML and OPA are general-purpose and have no built-in notion of taint provenance, injection-detector scores or tool-parameter semantics. Mirsad's policy format adds these as first-class attributes while keeping the PEP/PDP separation.
- **Tamper-evident logging of agent actions.** Secure logging research targets system and forensic logs. Applying hash-chained, keyed audit trails to agent tool calls and approval decisions, with secrets redacted before hashing, is a new application that supports forensics after a prompt-injection incident. (Mirsad's audit writer redacts secrets, then truncates, chains and stores each event.)
- **Measured cost of human-in-the-loop security.** HCI guidelines and KLM are rarely applied to security approvals for AI agents. Mirsad can contribute a KLM estimate and measured approval times, plus approval-accuracy data, for a mobile and bilingual approval workflow.
- **Bilingual (Arabic/English) documentation and accessibility.** Datasheets, model cards and WCAG are language-neutral frameworks. Mirsad's Arabic coverage, including dialects, code-switching and RTL presentation, requires reporting broken down by language and direction-aware accessibility work that the foundational sources ask for in principle but do not demonstrate.

### Limitations of this track

The ISO/IEC/IEEE standards were checked against the IEC webstore catalogue records only, because their full texts are paid. Content statements about those standards are therefore limited to their published scope and widely documented structure. The W3C Web App Manifest and Service Workers documents are living drafts, cited at their versions current on 11 October 2026, and should be re-checked before the final report. The KLM operator values used in [17] (M = 1.35 s, P = 1.10 s, H = 0.40 s, K = 0.08–1.20 s) were checked against the original paper. They were calibrated for keyboard-and-mouse desktop systems, so touch-screen values for the mobile approval app must come from later work or from the team's own measurements.

## Verification log

Independent fact-check, 11 October 2026. Every reference was re-checked against an authoritative record. Corrections were made in place.

**What was checked**

- **DOI metadata (Crossref API)** for [1], [2], [4], [5], [6], [8], [14]–[19], [23], [24]. Authors, title, venue, volume, issue, pages and year all match. The month for [4] (Sep. 1975) is confirmed by library catalogue records for Proc. IEEE 63(9).
- **RFC Editor metadata** for [8], [23], [24]: status (Informational, Proposed Standard, Informational), date, DOI and "updated by" fields (RFC 6151 for 2104; RFC 7797 and 8725 for 7519; none for 7914). The texts of RFC 2104 and RFC 7914 were checked for truncation, sample code and test vectors (2104), and for Salsa20/8, BlockMix, ROMix, the ASN.1 module and the denial-of-service warning (7914).
- **Full texts or official abstracts**: [1] (explicit and implicit flows, program certification), [2] (abstract, the four trends, the declassification discussion), [3] (NDSS page: TaintCheck, run-time binary rewriting, no false positives), [6] (authors' paper: key evolution, hash chain, MACs, "detect, not prevent" deletion), [7] (paper PDF: 800 MB vs 3 KB proofs for 80M events, 1,750 events/s on one core and 10,500 events/s with signatures offloaded, gossip of commitments), [13] (arXiv v3 is the ICLR camera-ready version; ICLR page lists it as a notable-top-5% paper), [14] (NeurIPS abstract), [15] (Microsoft Research page: 18 guidelines, 49 practitioners, 20 products, CHI 2019 Honorable Mention), [17] (original CACM scan: 10 systems, 21 percent error, operator times).
- **Official pages**: NDSS 2005 (12th symposium, San Diego), USENIX Security '09 event page and BibTeX, OASIS XACML 3.0 (core spec and Plus Errata 01), OPA Policy Language docs and the CNCF graduation press release (4 Feb 2021), Wiley product page, Microsoft Learn (updated 4 Mar 2026), W3C TR pages and publication histories for WCAG 2.2, Web App Manifest and Service Workers, IEC webstore entries for 29148:2018 and 29119-1:2022, ISO/IEC listings for 29119-2/3/4:2021, standards preview tables of contents for 29148:2018 and 29119-4:2021, and scrumguides.org.
- **Mirsad source code**: the claims about scrypt parameters (ln=14, r=8, p=1, PHC format), HS256 JWTs with pinned algorithm and issuer, a separately derived audit HMAC key, the HMAC-SHA256 `prev_hash` chain with an external anchor, redaction before truncation, `worker-src 'self'`, `no-store` on API responses and the manifest link were checked in `src/mirsad/auth.py`, `src/mirsad/audit/log.py`, `src/mirsad/api/security.py` and `web/approve.html`.

**What was changed**

- [2]: The trends now follow the paper (expressiveness, concurrency, covert channels, refined policies). "Controlled release" is replaced by the paper's own term, declassification (downgrading).
- [3]: Added the confirmed location, San Diego, CA, USA.
- [5]: Removed the claim that the paper assumes an "anchored latest link" and that Mirsad's anchor "follows directly" from the paper. The paper instead relies on copies held by other clients, which is now described as an analogy.
- [8]: Removed the claim that HMAC's analysis "does not depend on collision resistance". RFC 2104 §6 relies on a weak, secret-key form of collision resistance, and the text now says so.
- [9]: Named the 2017 edition precisely: Plus Errata 01, 12 July 2017.
- [10]: The URL `/docs/latest/policy-language/` now redirects (301), so the reference uses the canonical `/docs/policy-language`.
- [11]: Added the publisher city (Indianapolis, IN, USA), confirmed from the Wiley front matter of the author's sample chapter. Replaced the later wording of the four questions with the 2014 wording, as confirmed by the IEEE Cipher review. Aligned the author's role with the Wiley bio and noted the second edition announced for January 2027.
- [12]: Corrected the page title. Removed two claims the cited page does not make: the STRIDE-to-property mapping and that the tool "generates threats from a data-flow diagram". The mapping is now attributed to Shostack's Table B-0 (STRIDE-per-element).
- [17]: Replaced "about 21 percent" with the paper's "21 percent". Added the operator times confirmed in the original paper, and updated the Limitations paragraph to match.
- [20]: Added W3C's caveat on 4.1.1 Parsing to the backward-conformance sentence.
- [24]: Replaced "(GPUs, ASICs)" with the RFC's "custom-designed parallel hardware". The claim that rate limiting addresses the RFC's denial-of-service concern was wrong: the RFC warns about attacker-supplied large parameters. The text now cites Mirsad's parameter bounds for that concern and the login throttle as a separate control.
- No changes were needed to [1], [4], [6], [7], [13]–[16], [18], [19], [21]–[23], [25]–[27]. One discrepancy is recorded for [6]: Schneier's own site lists "vol. 1, no. 3", but the Crossref/ACM record (vol. 2, no. 2, May 1999) is used.

**Still unconfirmed**: the page range of [7] in the USENIX Security 2009 proceedings (not on the USENIX page or in its BibTeX) is still omitted. The full texts of the paid ISO/IEC/IEEE standards [25], [26] were not read. Statements about them rely on the publishers' scope text and the preview tables of contents.
