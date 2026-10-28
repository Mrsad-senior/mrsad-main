# Multilingual and Arabic LLM Security, Arabic NLP, Standards and Saudi Regulation

*Research track: multilingual-arabic-security-and-standards. Mirsad (مرصاد) IS499 Senior Project, Prince Sultan University, 2026-2027. Compiled 11 October 2026.*

## Introduction

Mirsad has to work in two languages and under two sets of rules. On the language side, the firewall's injection detector must catch attacks written in Arabic, in English, and in the mixed forms that Saudi users actually type: Gulf dialect, code-switched Arabic-English, and Arabic written in Latin letters (Arabizi). On the governance side, a Saudi deployment answers to national law (the Personal Data Protection Law), to national cybersecurity controls (the NCA's Essential Cybersecurity Controls) and to SDAIA's AI ethics and generative-AI guidance, while the engineering community describes the threat with international references such as OWASP, NIST, MITRE ATLAS and ISO/IEC. This track collects the primary sources for both sides. Part A covers multilingual and Arabic LLM security: the jailbreak studies that showed safety training does not transfer evenly across languages, the Arabic safety benchmarks published between 2025 and 2026, and the small amount of work on Arabic prompt injection and Arabic tool use. Part B covers the Arabic and multilingual language models that a detector can be built on. Part C covers the international standards and threat frameworks, together with the Model Context Protocol specification that Mirsad intercepts. Part D covers Saudi regulation and national strategy. The synthesis at the end draws out themes and research gaps, and maps each standard or regulation to the Mirsad features that help an adopting organization comply with it.

**How the sources were checked.** Each reference was checked against a reachable authoritative record: the ACL Anthology for ACL, EMNLP, NAACL, WANLP, OSACT and TrustNLP papers; arXiv abstract pages (including the journal-reference field) for preprints; the NIST CSRC and nist.gov publication pages and the NIST PDFs themselves; the OWASP GenAI Security Project site; the official MITRE ATLAS data repository changelog; the IEC webstore records for the ISO/IEC standards (iso.org blocked automated access); the MCP specification site; the NCA, SDAIA and Vision 2030 PDFs on their official servers; and the Saudi Bureau of Experts (laws.boe.gov.sa) page for the PDPL. Where a detail could only be confirmed from a secondary source (a law-firm briefing, a regulatory tracker or a compliance guide), the entry says so. Details that could not be confirmed, such as the month of some proceedings, were left out rather than guessed. The ISO/IEC standards are paywalled, so statements about their Annex A controls come from public summaries and should be checked against a licensed copy before they are cited in the final report. An independent fact-check pass on 11 October 2026 re-confirmed every entry against these sources and corrected the details listed in the Verification log at the end of this document.

---

## A. Multilingual and Arabic LLM security

### [1] Yong, Menghini and Bach (2023): low-resource languages jailbreak GPT-4

**Reference.** Z.-X. Yong, C. Menghini, and S. H. Bach, "Low-resource languages jailbreak GPT-4," presented at the NeurIPS 2023 Workshop on Socially Responsible Language Modelling Research (SoLaR), 2023, arXiv:2310.02446. [Online]. Available: https://arxiv.org/abs/2310.02446

**Summary.** The authors took the 520 harmful instructions of the AdvBench "harmful behaviors" set, machine-translated them with the Google Translate API into twelve languages grouped by resource level, and sent them to GPT-4. When the four low-resource languages (Zulu, Scots Gaelic, Hmong, Guarani) were combined, GPT-4 produced actionable harmful content about 79% of the time, comparable to the best jailbreak methods of the time. Mid- and high-resource languages had much lower bypass rates. Modern Standard Arabic was placed in the high-resource group and had a bypass rate of only 3.65%. The paper won a best-paper award at the workshop and argues that the safety gap for low-resource languages is a risk for every user, because anyone can translate an attack.

**Strengths and limitations.** It is a simple, reproducible attack that exposed a structural weakness in safety training, and its per-language results are reported in full. It tests a single 2023 model snapshot with machine translation and no adaptive attacker, and its Arabic result covers only MSA, not dialects or Arabizi.

**Relevance to Mirsad.** It is the starting reference for the claim that a firewall cannot rely on the model's own refusal behavior once the language changes. Its low Arabic bypass rate is also a warning: MSA alone is not the hard case. The harder cases are the less standard forms of Arabic covered in [3], [6]–[8].

### [2] Deng, Zhang, Pan and Bing (2024): multilingual jailbreak challenges

**Reference.** Y. Deng, W. Zhang, S. J. Pan, and L. Bing, "Multilingual jailbreak challenges in large language models," in *Proc. 12th Int. Conf. Learn. Represent. (ICLR)*, 2024. [Online]. Available: https://arxiv.org/abs/2310.06474

**Summary.** The paper separates two threat scenarios: *unintentional*, where an ordinary user writing in a non-English language gets unsafe output, and *intentional*, where an attacker combines a harmful instruction with a multilingual prompt on purpose. The authors built MultiJail, 315 English unsafe prompts translated by native speakers into nine languages; Arabic is one of the three medium-resource languages. In the unintentional case, low-resource languages produced roughly three times as much unsafe content as high-resource ones for both ChatGPT and GPT-4. In the intentional case, multilingual prompts raised unsafe output to 80.92% for ChatGPT and 40.71% for GPT-4. The authors also propose "Self-Defense," a method that generates multilingual safety-tuning data automatically and reduced unsafe output after fine-tuning.

**Strengths and limitations.** Human translation (rather than machine translation) and a clear two-scenario threat model make it a widely cited peer-reviewed reference in this area. Its defense requires fine-tuning the model, which a deployer of a closed API model cannot do, and it does not study tool-using agents.

**Relevance to Mirsad.** The unintentional scenario is the reason Mirsad's detector must handle benign Arabic traffic well: Arabic users are not attackers by default, so false positives on normal Arabic would make the product unusable. MultiJail's Arabic split is a ready-made, human-translated test set for the detector's Arabic jailbreak recall.

### [3] Al Ghanim et al. (2024): jailbreaking LLMs with Arabic transliteration and Arabizi

**Reference.** M. Al Ghanim, S. Almohaimeed, M. Zheng, Y. Solihin, and Q. Lou, "Jailbreaking LLMs with Arabic transliteration and Arabizi," in *Proc. 2024 Conf. Empirical Methods Natural Lang. Process. (EMNLP)*, Miami, FL, USA, Nov. 2024, pp. 18584–18600, doi: 10.18653/v1/2024.emnlp-main.1034.

**Summary.** The authors translated AdvBench into Arabic (with GPT-3.5 Turbo, then proofread) and tested GPT-4 and Claude 3 Sonnet in three forms: standard Arabic script, transliteration into Latin characters, and Arabizi chatspeak (which also uses digits such as 3 and 7 for Arabic letters). Standard Arabic, even with prefix injection, did not get the models to produce unsafe content. The transliterated and Arabizi versions did. The authors suggest that the models learned refusal associations tied to particular words in their usual script, so a change of script hides those triggers. They call for safety training that covers every written form of a language.

**Strengths and limitations.** It is the most directly relevant peer-reviewed Arabic attack paper and it identifies a concrete, cheap evasion technique; the authors note that chatspeak is widely used by young Arabic speakers online. It studies jailbreaks of the model itself, not injection through tool outputs, and the tested model versions have since been replaced.

**Relevance to Mirsad.** Mirsad's detector must normalize or explicitly model Arabizi and transliterated Arabic; a classifier trained only on Arabic script would miss exactly the inputs this paper shows to be most dangerous. The paper also justifies keeping deterministic controls (policy and taint tracking) in front of the classifier, because script-switching can defeat any learned filter.

### [4] Ashraf et al. (2025): Arabic dataset for LLM safeguard evaluation

**Reference.** Y. Ashraf, Y. Wang, B. Gu, P. Nakov, and T. Baldwin, "Arabic dataset for LLM safeguard evaluation," in *Proc. 2025 Conf. Nations Americas Chapter Assoc. Comput. Linguistics: Human Lang. Technol. (NAACL), Vol. 1 (Long Papers)*, Albuquerque, NM, USA, Apr. 2025, pp. 5529–5546, doi: 10.18653/v1/2025.naacl-long.285.

**Summary.** The authors adapted a Chinese safety-evaluation dataset to Arabic, localizing general questions and adding harm types specific to the Arab region. They wrote 1,024 sensitive direct-attack questions and expanded them with indirect-attack versions and harmless questions that contain sensitive words, for 5,799 questions in total. Because politically sensitive answers can be judged differently, they score responses from both a governmental and an oppositional perspective. Testing five Arabic-centric and multilingual LLMs showed large differences in safety behavior between models.

**Strengths and limitations.** It is one of the first peer-reviewed, culturally grounded Arabic safety sets, and the harmless-but-sensitive questions directly measure over-refusal. It evaluates chat responses only and does not cover tool use or indirect injection.

**Relevance to Mirsad.** The harmless-with-sensitive-words subset is a good false-positive test for Mirsad's Arabic detector, which must not flag benign Arabic text just because it mentions religion, politics or security. The dual-perspective idea is also a reminder that "harm" labels in Arabic depend on local context, which matters when Mirsad's policies are written for Saudi organizations.

### [5] Mubarak, Mohamed and Hawasly (2025): AraSafe

**Reference.** H. Mubarak, A. Mohamed, and M. Hawasly, "AraSafe: Benchmarking safety in Arabic LLMs," in *Findings Assoc. Comput. Linguistics: EMNLP 2025*, Suzhou, China, Nov. 2025, pp. 9976–9992, doi: 10.18653/v1/2025.findings-emnlp.529.

**Summary.** AraSafe contains about 12,000 naturally occurring, human-written Arabic prompts, both harmful and harmless, drawn from varied domains. Two experts independently labeled each prompt into one of nine safety categories. Because harmful examples were scarce, the authors added about 12,000 synthetic harmful prompts generated with GPT-4o to train classifiers. They evaluated Arabic-centric and multilingual models in the 7-13B range and BERT-based harmful-prompt classifiers, using GPT-4o as an upper-bound reference, and found clear safety blind spots in Arabic LLMs.

**Strengths and limitations.** Native (not translated) prompts with double expert annotation make it a strong benchmark for real Arabic usage, and it reports classifier baselines that are directly comparable to a detector. It targets harmful *requests* rather than injected *instructions*, and its synthetic half was produced by one model, which can bias a classifier trained on it.

**Relevance to Mirsad.** AraSafe is the most useful public source of natural Arabic text for training and testing the "benign" side of Mirsad's detector, and its BERT-classifier baselines give the team a published number to compare against.

### [6] Abdelnasser et al. (2026): SalamahBench

**Reference.** O. Abdelnasser, F. Alharbi, K. Khasawneh, I. Alouani, and M. E. Fouda, "SalamahBench: Dialect and category level safety evaluation of Arabic language models," arXiv:2603.04410, 2026. [Online]. Available: https://arxiv.org/abs/2603.04410

**Summary.** SalamahBench has 8,270 human-verified harmful prompts organized by MLCommons hazard categories, each written in MSA and in five regional varieties (Egyptian, Syrian, Saudi, Lebanese and Moroccan), for 49,620 paired items. The authors define two metrics: Dialect Shift, the overall change in a model's safety when a prompt is reworded into a dialect, and Category-Specific Dialect Deviation, which flags harm categories that move against that overall trend. They evaluate the regional models Fanar 2, ALLaM 2 and Karnak 1 under several safeguard settings. Robustness across varieties depends strongly on the model, and aggregate scores can hide large changes inside individual categories.

**Strengths and limitations.** It is one of very few benchmarks that includes a Saudi dialect split, and the paired design isolates the effect of dialect from the effect of content. It is still a preprint (revised to v3 in September 2026) and evaluates harmful requests, not tool-mediated injection.

**Relevance to Mirsad.** The Saudi split is the closest public match to the language Mirsad's users will actually write, and the paired MSA/dialect design is a good template for Mirsad's own detector evaluation: report results per dialect and per category, not only as one average.

### [7] Zaghouani (2026): toward dialect-aware safety evaluation for Arabic LLMs

**Reference.** W. Zaghouani, "Toward dialect-aware safety evaluation for Arabic large language models," in *Proc. 6th Workshop Trustworthy NLP (TrustNLP)*, San Diego, CA, USA, Jul. 2026, pp. 503–514, doi: 10.18653/v1/2026.trustnlp-main.37.

**Summary.** The paper points out that most Arabic speakers communicate day to day in regional dialects, while alignment data and safety benchmarks favor MSA. It defines a "Dialect Safety Gap" as differences in a model's safety behavior across dialects of the same language and frames it as a fairness problem. It proposes a binary DSG score, a magnitude-aware Pairwise Dialect Inconsistency measure and an evaluation protocol called DASEP. A human-annotated probe (20 base prompts rendered in five Arabic variety groups) shows a structured pattern of safety degradation whose endpoints, in the author's words, are consistent with linguistic distance from MSA.

**Strengths and limitations.** It gives the field a vocabulary and metrics for dialect gaps that can be reused by other projects. The empirical part is a small probe rather than a full benchmark, so the strength of the effect needs confirmation.

**Relevance to Mirsad.** The DSG and pairwise-inconsistency metrics can be applied directly to Mirsad's detector: the team can report whether detection rates differ between MSA, Gulf and other dialects, which is both a security and a fairness requirement under SDAIA's principles [34].

### [8] Zaghouani et al. (2026): ArabicDialectSafety

**Reference.** W. Zaghouani, M. R. Biswas, K. K. Aldous, and M. Bessghaier, "ArabicDialectSafety: A dialect-aware benchmark for Arabic content safety classification," in *Findings Assoc. Comput. Linguistics: EMNLP 2026*, to appear; arXiv:2608.01291, 2026. [Online]. Available: https://arxiv.org/abs/2608.01291

**Summary.** The dataset contains roughly 24,000 to 25,000 human-curated prompts in MSA and five dialects (Syrian, Egyptian, Algerian, Palestinian and Moroccan); the arXiv abstract gives 25,071, while the abstract and dataset table inside the current PDF (v2) give 24,051. Each prompt is labeled with its dialect and one of seven harm categories, with benign counterparts. The authors evaluate binary safe/unsafe detection and fine-grained harm classification. A fine-tuned MARBERTv2 performed best (macro-F1 of 0.95 for binary and 0.90 for fine-grained), ahead of prompted frontier LLMs, including Arabic-specialized ones. Performance was weaker on the low-resource Maghrebi dialects. When seven frontier LLMs were asked to answer the harmful dialectal prompts, their unsafe-answer rates stayed below 5%.

**Strengths and limitations.** It shows, with a large human-curated set, that a small fine-tuned Arabic encoder can beat prompted large models at Arabic safety classification. It has no Gulf or Saudi split, and the authors said the data would be released upon acceptance (the ArGuard overview [10] describes access to the derived Track B data as controlled).

**Relevance to Mirsad.** This is strong evidence for Mirsad's design choice of a compact, fine-tuned Arabic/English classifier rather than an LLM-as-judge in the hot path: it is cheaper, faster and, on this evidence, more accurate. MARBERTv2 [17] is therefore a serious candidate backbone.

### [9] Abed et al. (2026): red-teaming leading Arabic LLMs with ASAS

**Reference.** F. Abed, H. Khan, M. S. Bari, B. Khan, and A. Abujabal, "Redteaming leading Arabic LLMs with ASAS," arXiv:2608.21985, Aug. 2026. [Online]. Available: https://arxiv.org/abs/2608.21985

**Summary.** ASAS (Arabic Safety Index) is a fully human-curated red-teaming benchmark of 801 prompts covering eight safety categories and eight attack strategies, with ideal answers written in MSA. Seven Arabic-capable models were tested, including GPT-4o, Claude 3.7 Sonnet and the regional models ALLaM and FANAR, and human annotators scored responses on a four-point scale. Most models failed to defend against about half of the unsafe prompts, with the worst results in high-harm areas such as weapons and illicit substances. Direct and obfuscation-based attacks were the most effective, and GPT-4o as an automatic judge agreed poorly with the human annotators.

**Strengths and limitations.** Human scoring and attack-strategy labels make it more realistic than single-turn harmful-request sets. It is small and a recent preprint, and its eight attack types (direct prompting, step-by-step escalation, code/encryption, hypothetical testing, storytelling, false premise, persona/roleplay and out-of-context) do not include prompt injection.

**Relevance to Mirsad.** Its result that obfuscation-based attacks work best in Arabic supports Mirsad's plan to normalize text (script, diacritics, elongation, Arabizi) before classification. Its finding that LLM judges disagree with humans is a caution for Mirsad's evaluation: detector accuracy should be measured against human labels, not GPT-graded labels.

### [10] Alam et al. (2026): ArGuard shared task

**Reference.** F. Alam, M. R. Biswas, M. B. Kmainasi, A. E. Shahroor, H. Mubarak, G. Mikros, A. Hasnat, and W. Zaghouani, "ArGuard shared task: Harmful content detection in Arabic memes and LLM prompts," arXiv:2609.29349, Sep. 2026. [Online]. Available: https://arxiv.org/abs/2609.29349

**Summary.** This overview reports a community shared task with two tracks; Track B is harmful-prompt detection for Arabic LLM safety, with a binary safe/unsafe subtask (B1) and a seven-class harm-category subtask (B2). Training and development data came only from ArabicDialectSafety [8], and the test set combined it with 5,981 AraSafe [5] test-set prompts. Of 58 registered teams, 35 took part in the final evaluation, using models such as AraBERT, Jais and Qwen3-VL. The best macro-F1 scores were 0.984 on B1 and 0.790 on B2, and the organizers note that some label mappings between the two source datasets were imperfect.

**Strengths and limitations.** It provides a public leaderboard and many system descriptions for exactly the task of classifying Arabic prompts, which shortens the team's literature search for detector architectures. Track B data is under controlled access, and the overview does not say that injection or jailbreak prompts are included.

**Relevance to Mirsad.** It gives Mirsad realistic upper bounds for Arabic harmful-prompt classification and a list of winning recipes to borrow. It also highlights a gap: there is still no Arabic shared task for *prompt-injection* detection, which is what Mirsad actually needs.

### [11] Theocharopoulos, Kulkarni and Magimai.-Doss (2025): multilingual hidden prompt injection in LLM reviewing

**Reference.** P. Theocharopoulos, A. Kulkarni, and M. Magimai.-Doss, "Multilingual hidden prompt injection attacks on LLM-based academic reviewing," arXiv:2512.23684, Dec. 2025. [Online]. Available: https://arxiv.org/abs/2512.23684

**Summary.** The authors took about 500 real accepted ICML papers and hid semantically equivalent adversarial instructions inside each one in four languages: English, Japanese, Chinese and Arabic. An LLM then reviewed each document. English, Japanese and Chinese injections substantially changed review scores and accept/reject decisions, but Arabic injections had little or no effect. The authors conclude that susceptibility to document-level injection varies by language.

**Strengths and limitations.** It is one of the very few studies of *indirect* prompt injection, the attack Mirsad targets, that includes Arabic. It covers one task (reviewing), one reviewing setup, and does not explain the Arabic result, which may reflect weaker Arabic instruction-following rather than stronger defenses.

**Relevance to Mirsad.** It is a useful counterpoint to [1]–[3]: Arabic content does not always make attacks easier. For Mirsad this means the risk depends on how well the backing model follows Arabic instructions, so as Arabic-capable models improve (see [12], [19]), Arabic injections should be expected to become more effective, not less.

### [12] Kubrak et al. (2026): Arabic prompts with English tools

**Reference.** K. Kubrak, A. El-Moselhy, A. Alsulami, R. Altuwaim, H. I. Fawaz, and F. Alsaby, "Arabic prompts with English tools: A benchmark," presented at the LLMs, Big Data, and Multilinguality for All (LLMs4All) Workshop, IEEE BigData 2025, Macau, Dec. 2025, arXiv:2601.05101. [Online]. Available: https://arxiv.org/abs/2601.05101

**Summary.** The paper presents what the authors describe as the first benchmark for LLM tool calling and agentic behavior in Arabic. It provides a standardized framework to measure the functional accuracy and robustness of models in Arabic agent workflows. The main finding is that tool-calling accuracy drops by roughly 5-10% on average when the user interacts in Arabic. The drop occurs whether the tool descriptions are written in Arabic or in English.

**Strengths and limitations.** It addresses the exact deployment pattern Mirsad protects (Arabic user, English tool schemas) and measures it directly. It is a workshop paper that measures accuracy, not security, so it does not test any attack.

**Relevance to Mirsad.** Lower tool-calling accuracy in Arabic means more malformed or unexpected tool arguments. Mirsad's per-parameter policy checks (types, allow-lists, value ranges) therefore protect against honest Arabic-induced errors as well as attacks, and the team should expect more policy-triggered blocks in Arabic sessions when tuning thresholds.

### [13] Muhtadi and Tazwar (2026): MIPIAD multilingual indirect prompt-injection defense

**Reference.** A. M. Muhtadi and M. R. Tazwar, "MIPIAD: Multilingual indirect prompt injection attack defense with Qwen–TF-IDF hybrid and meta-ensemble learning," arXiv:2605.07269, May 2026. [Online]. Available: https://arxiv.org/abs/2605.07269

**Summary.** MIPIAD detects indirect prompt injection with a hybrid of a sequence classifier (XLPID, fine-tuned from Qwen2.5-1.5B with LoRA) and TF-IDF lexical features, combined through late fusion, stacking and gradient boosting. It is trained and tested on a synthetic set of over 1.43 million samples built from BIPIA templates across email, table, question-answering, abstract and code tasks, with attack categories kept disjoint between training and test splits. TF-IDF with an SVM alone reached an F1 of 0.77; the hybrid ensemble reached the best F1 (0.9205) and a boosting ensemble the best AUROC (0.9378). Ensembles also narrowed the gap between English and Bangla.

**Strengths and limitations.** It is the closest published design to Mirsad's detector: multilingual, aimed at *indirect* injection in tool-like content, and built on Qwen2.5. Its evaluation covers only English and Bangla (Arabic is not tested), and the data are synthetic templates.

**Relevance to Mirsad.** It is a ready architectural baseline (small Qwen2.5 backbone plus cheap lexical features) and a data-generation recipe that the team can repeat for Arabic and Arabizi. Using disjoint attack categories between train and test is a good practice for Mirsad's own evaluation.

### [14] Meta: Llama Prompt Guard 2 model card

**Reference.** Meta, "Llama Prompt Guard 2 86M," model card, Hugging Face. [Online]. Available: https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M (accessed Oct. 11, 2026).

**Summary.** Prompt Guard 2 is a small classifier (86M parameters, multilingual mDeBERTa backbone) that labels a prompt as malicious or benign when it explicitly tries to override earlier instructions, covering both prompt injection and jailbreaks. The model card lists eight supported languages: English, French, German, Hindi, Italian, Portuguese, Spanish and Thai. Its limitations section lists adaptive attacks designed to evade it and sensitivity to application-specific prompts (fine-tuning on application data is recommended), and its model-scope section notes a 512-token context window, so longer inputs must be split into segments.

**Strengths and limitations.** It is a widely used, openly available industry baseline that shows what a production prompt-injection classifier looks like. Arabic is not among its supported languages.

**Relevance to Mirsad.** It is the natural off-the-shelf baseline to beat on English and the clearest evidence of the Arabic gap Mirsad fills. Its 512-token limit is also a design note: Mirsad must chunk long tool outputs (web pages, emails) before classifying them.

---

## B. Arabic and multilingual language-model foundations

### [15] Antoun, Baly and Hajj (2020): AraBERT

**Reference.** W. Antoun, F. Baly, and H. Hajj, "AraBERT: Transformer-based model for Arabic language understanding," in *Proc. 4th Workshop Open-Source Arabic Corpora Process. Tools (OSACT4), with a Shared Task on Offensive Language Detection*, Marseille, France, May 2020, pp. 9–15.

**Summary.** The authors note that Arabic's rich morphology and limited resources make tasks such as sentiment analysis, named-entity recognition and question answering harder than in English. They pretrain BERT specifically on Arabic text and compare it with Google's multilingual BERT and other approaches. AraBERT achieves state-of-the-art results on most of the Arabic tasks they test. The models were released publicly and became a standard Arabic baseline.

**Strengths and limitations.** It is the canonical, widely reproduced Arabic encoder with good tooling and many fine-tuned variants. Its pretraining is mainly MSA, so dialectal and Arabizi text is weaker, and it predates the instruction-following attacks Mirsad faces.

**Relevance to Mirsad.** AraBERT is a strong, cheap baseline for the Arabic detector and was used by several ArGuard teams [10]. Comparing it against dialect-aware encoders [16], [17] will show whether Mirsad needs dialect coverage in the backbone.

### [16] Inoue et al. (2021): CAMeLBERT, variant, size and task type

**Reference.** G. Inoue, B. Alhafni, N. Baimukan, H. Bouamor, and N. Habash, "The interplay of variant, size, and task type in Arabic pre-trained language models," in *Proc. 6th Arabic Natural Lang. Process. Workshop (WANLP)*, Kyiv, Ukraine (Virtual), Apr. 2021, pp. 92–104.

**Summary.** The paper introduces the CAMeLBERT models, pretrained separately on Modern Standard Arabic, dialectal Arabic, classical Arabic and a mixture of the three, plus scaled-down MSA versions. The mixed model was trained on 167 GB of text (about 17.3 billion words). The authors fine-tune these and eight public models on five task types over twelve datasets. Their main finding is that how closely the pretraining variant matches the fine-tuning data matters more than the amount of pretraining data, and they use this to build a model-selection method.

**Strengths and limitations.** It gives an evidence-based rule for choosing an Arabic backbone and offers matched models that differ only in variant. It does not test security tasks or Arabizi.

**Relevance to Mirsad.** It tells the team to choose the detector backbone by matching it to the language of Mirsad's traffic (Gulf dialect, MSA and English mixed) rather than simply picking the largest model. The CAMeLBERT-DA and -Mix variants are natural candidates to test against MSA-centric models.

### [17] Abdul-Mageed, Elmadany and Nagoudi (2021): ARBERT and MARBERT

**Reference.** M. Abdul-Mageed, A. Elmadany, and E. M. B. Nagoudi, "ARBERT & MARBERT: Deep bidirectional transformers for Arabic," in *Proc. 59th Annu. Meeting Assoc. Comput. Linguistics and 11th Int. Joint Conf. Natural Lang. Process. (ACL-IJCNLP), Vol. 1 (Long Papers)*, Online, Aug. 2021, pp. 7088–7105, doi: 10.18653/v1/2021.acl-long.551.

**Summary.** The authors argue that multilingual models are expensive at inference time and have limited non-English pretraining data. They introduce two Arabic encoders, ARBERT and MARBERT, designed to cover Arabic's many varieties, and ARLUE, a benchmark of 42 datasets in six task clusters for multi-dialect Arabic understanding. Fine-tuned on ARLUE, their models set new results on most classification tasks and their best model achieves the top overall ARLUE score, beating larger models such as XLM-R Large. The models are publicly released.

**Strengths and limitations.** It provides dialect-aware encoders and a broad benchmark, and the later MARBERTv2 was the best model in ArabicDialectSafety [8]. Like the other encoders it was not designed for adversarial inputs.

**Relevance to Mirsad.** Given its result in [8], MARBERTv2 is the leading candidate backbone for the Arabic half of Mirsad's detector, especially for Gulf dialect and social-media-style text.

### [18] Conneau et al. (2020): XLM-R

**Reference.** A. Conneau, K. Khandelwal, N. Goyal, V. Chaudhary, G. Wenzek, F. Guzmán, E. Grave, M. Ott, L. Zettlemoyer, and V. Stoyanov, "Unsupervised cross-lingual representation learning at scale," in *Proc. 58th Annu. Meeting Assoc. Comput. Linguistics (ACL)*, Online, Jul. 2020, pp. 8440–8451, doi: 10.18653/v1/2020.acl-main.747.

**Summary.** The paper trains XLM-R, a Transformer masked language model, on more than two terabytes of filtered web text in 100 languages. XLM-R outperforms multilingual BERT on cross-lingual benchmarks, with the largest gains on XNLI, MLQA and named-entity recognition, and it does well on low-resource languages. The authors analyze the trade-off between sharing capacity across many languages and per-language quality (the "curse of multilinguality"). They show XLM-R stays competitive with strong monolingual models on GLUE and XNLI.

**Strengths and limitations.** A single model covers Arabic and English, which suits code-switched input and simplifies deployment. Per-language capacity is diluted across 100 languages, and [17] reports that dedicated Arabic encoders beat it on Arabic tasks.

**Relevance to Mirsad.** XLM-R is the natural single-model baseline for a bilingual detector. If it comes close to the Arabic-specific encoders on Mirsad's test set, one multilingual model is simpler to deploy than two language-specific ones.

### [19] Qwen Team (2024): Qwen2.5 technical report; and [20] Qwen2.5-7B-Instruct model card

**References.**
[19] A. Yang *et al.* (Qwen Team), "Qwen2.5 technical report," arXiv:2412.15115, Dec. 2024 (rev. Jan. 2025). [Online]. Available: https://arxiv.org/abs/2412.15115
[20] Qwen Team, "Qwen2.5-7B-Instruct," model card, Hugging Face. [Online]. Available: https://huggingface.co/Qwen/Qwen2.5-7B-Instruct (accessed Oct. 11, 2026).

**Summary.** Qwen2.5 is a family of open-weight base and instruction-tuned models in several sizes, with pretraining data increased from 7 trillion to 18 trillion tokens and post-training using over a million supervised examples and multi-stage reinforcement learning. The report evaluates Arabic explicitly: Qwen2.5-72B-Instruct scores 72.44 on the Arabic AMMLU benchmark (59.78 for the 7B model), and the authors extended the MGSM math benchmark to include Arabic. The model card states support for more than 29 languages including Arabic, a 131,072-token context window, and improved structured (JSON) output.

**Strengths and limitations.** Open weights, small sizes, documented Arabic results and reliable JSON output make it practical both as a detector backbone and as the agent model in Mirsad's test bed. Its Arabic ability is measured with MSA knowledge and math benchmarks, not dialects or safety, and the technical report does not list all 29 languages.

**Relevance to Mirsad.** Qwen2.5 is a strong candidate for two roles: the small backbone of an LLM-based injection classifier (as MIPIAD [13] does with Qwen2.5-1.5B) and the agent under test when the team measures how often Arabic injections succeed with and without Mirsad.

---

## C. International standards, threat frameworks and protocol specifications

### [21] OWASP (2024): Top 10 for LLM Applications 2025 (LLM01 Prompt Injection, LLM06 Excessive Agency)

**Reference.** OWASP GenAI Security Project, "OWASP Top 10 for LLM Applications 2025," OWASP Foundation, Nov. 2024. [Online]. Available: https://genai.owasp.org/resource/owasp-top-10-for-llm-applications-2025/

**Summary.** The 2025 list, published in November 2024, keeps Prompt Injection as LLM01 and adds System Prompt Leakage and Vector and Embedding Weaknesses. LLM01 distinguishes *direct* injection (the user's own prompt) from *indirect* injection (instructions hidden in external content such as web pages or files), and includes a scenario where attackers use multiple languages or encodings to slip past filters. Its seven mitigation headings are constraining model behavior, defining and validating expected output formats, input and output filtering, privilege control and least-privilege access, human approval for high-risk actions, segregating and identifying external content, and adversarial testing; it says it is unclear whether fool-proof prevention methods for prompt injection exist. LLM06 Excessive Agency traces the root cause to excessive functionality, permissions or autonomy, and recommends minimizing extensions and their functionality and permissions, avoiding open-ended extensions, executing extensions in the user's context, requiring user approval, complete mediation in downstream systems and sanitizing inputs and outputs, with logging, monitoring and rate limiting listed separately as ways to limit damage.

**Strengths and limitations.** It is the most widely recognized industry reference and its mitigations are concrete enough to map to features. It is a community awareness document, not an auditable standard, and its guidance stays at a high level.

**Relevance to Mirsad.** Almost every LLM01 and LLM06 mitigation corresponds to a Mirsad feature: least privilege and complete mediation (policy engine), segregating untrusted content (taint tracking), filtering (detector), human approval (mobile approval app) and logging (audit chain). The multilingual scenario in LLM01 is an explicit citation for the Arabic detector.

### [22] OWASP Agentic Security Initiative (2025): Agentic AI – Threats and Mitigations

**Reference.** OWASP GenAI Security Project, Agentic Security Initiative, "Agentic AI – Threats and Mitigations," ver. 1.1, OWASP Foundation, Dec. 2025 (ver. 1.0 first published Feb. 2025). [Online]. Available: https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/

**Summary.** First published on 17 February 2025, this is the first guide in a series from OWASP's Agentic Security Initiative; the file now distributed from the resource page is version 1.1, dated December 2025. It gives a threat-model-based reference for threats that arise when LLMs act autonomously or semi-autonomously, with a T-numbered threat taxonomy (for example T1 Memory Poisoning, T2 Tool Misuse, T6 Intent Breaking and Goal Manipulation) and mitigations for each. It extends the LLM Top 10 from single model calls to agents that plan, use tools and keep memory. The Top 10 for Agentic Applications [23] maps each of its entries to these T-numbered threats.

**Strengths and limitations.** It offers the detailed threat vocabulary behind the shorter Top 10, which calls it OWASP's "foundational and detailed taxonomy." Its numbering differs from the ASI01–ASI10 numbering of [23], so a report should state which scheme it is using.

**Relevance to Mirsad.** It supports Mirsad's threat model chapter, in particular the treatment of tool misuse and of agent memory as attack surfaces.

### [23] OWASP (2025): Top 10 for Agentic Applications for 2026

**Reference.** OWASP GenAI Security Project, "OWASP Top 10 for Agentic Applications for 2026," OWASP Foundation, Dec. 2025. [Online]. Available: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

**Summary.** Released on 9 December 2025 with input from more than 100 experts, this list targets autonomous systems that plan and act across multi-step workflows. Its ten risks are ASI01 Agent Goal Hijack, ASI02 Tool Misuse and Exploitation, ASI03 Identity and Privilege Abuse, ASI04 Agentic Supply Chain Vulnerabilities, ASI05 Unexpected Code Execution (RCE), ASI06 Memory and Context Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI09 Human-Agent Trust Exploitation and ASI10 Rogue Agents. The full document pairs each risk with mitigations and architectural guidance.

**Strengths and limitations.** It is the current, agent-specific OWASP taxonomy and is directly about the tool-using setting Mirsad protects. Like [21], it is guidance rather than a certifiable standard, and it is new, so community mappings to it are still forming.

**Relevance to Mirsad.** Mirsad addresses ASI01 (goal hijack by injected content) through detection and taint tracking, ASI02 and ASI03 through per-tool, per-parameter policy, ASI04 by treating MCP tool descriptions as untrusted, and ASI09 by designing approval prompts that show concrete arguments and taint provenance instead of asking the human to trust the agent's summary.

### [24] NIST (2023): AI Risk Management Framework (AI RMF 1.0), NIST AI 100-1

**Reference.** E. Tabassi, "Artificial Intelligence Risk Management Framework (AI RMF 1.0)," National Institute of Standards and Technology, Gaithersburg, MD, USA, NIST AI 100-1, Jan. 2023, doi: 10.6028/NIST.AI.100-1.

**Summary.** Released on 26 January 2023, the AI RMF is a voluntary, sector-neutral framework for managing AI risk. It describes seven characteristics of trustworthy AI: valid and reliable; safe; secure and resilient; accountable and transparent; explainable and interpretable; privacy-enhanced; and fair with harmful bias managed. Its core organizes activities into four functions: Govern, Map, Measure and Manage. NIST added a Generative AI Profile (NIST AI 600-1) in July 2024, and the NIST AI RMF page states that the framework is being revised under the White House AI Action Plan.

**Strengths and limitations.** It is widely adopted and gives a neutral structure for an AI risk section in the project report. It is deliberately non-prescriptive, so it does not name specific controls, and a revision is pending.

**Relevance to Mirsad.** Mirsad can be presented as a "Manage" control for the "secure and resilient" and "accountable and transparent" characteristics, with its audit log and detector metrics supplying the evidence for "Measure."

### [25] Vassilev et al. (2025): NIST AI 100-2e2025, adversarial machine learning taxonomy

**Reference.** A. Vassilev, A. Oprea, A. Fordyce, H. Anderson, X. Davies, and M. Hamin, "Adversarial machine learning: A taxonomy and terminology of attacks and mitigations," National Institute of Standards and Technology, Gaithersburg, MD, USA, NIST AI 100-2e2025, Mar. 2025, doi: 10.6028/NIST.AI.100-2e2025.

**Summary.** The March 2025 edition (the latest final edition found on NIST CSRC as of this writing) organizes attacks on predictive and generative AI by lifecycle stage, attacker goals, capabilities and knowledge, and provides a glossary. Section 3.4 treats indirect prompt injection as an attack enabled by control over resources the model reads, because generative models mix data and instructions in one channel, and splits its effects into availability, integrity and privacy harms. Listed mitigations include training for instruction hierarchies, detection, filtering, "spotlighting" untrusted data, and designing systems on the assumption that injection will happen (for example, multiple models with different permissions, or access to untrusted data only through well-defined interfaces). Section 3.5 covers agents and notes that tool access lets attackers hijack agents to run code or exfiltrate data; the jailbreak discussion also lists translation into a less common language as a known technique.

**Strengths and limitations.** It is an authoritative, citable government taxonomy with stable identifiers. It is descriptive rather than prescriptive and says plainly that current mitigations do not give full protection.

**Relevance to Mirsad.** Mirsad is an instance of the "assume injection is possible and constrain the interface" design NIST describes. The report's terms (resource control, integrity violation, privacy compromise) should be used in Mirsad's threat model so the project uses standard vocabulary.

### [26] MITRE: ATLAS (Adversarial Threat Landscape for AI Systems)

**Reference.** MITRE Corporation, "MITRE ATLAS: Adversarial Threat Landscape for AI Systems," knowledge base, release 2026.09, Sep. 2026. [Online]. Available: https://atlas.mitre.org (release history: https://github.com/mitre-atlas/atlas-data)

**Summary.** ATLAS is a public knowledge base of adversary tactics, techniques and case studies against AI systems, modeled on MITRE ATT&CK. It defines LLM Prompt Injection (AML.T0051) with Direct (.000), Indirect (.001) and Triggered (.002) sub-techniques, and a growing set of agent techniques such as AI Agent Tool Invocation (AML.T0053) and Exfiltration via AI Agent Tool Invocation (AML.T0086). According to the official changelog, the March 2026 release added case studies on a poisoned MCP server and on exfiltration through a remote poisoned MCP tool, the August 2026 release added agent-specific mitigations, and the latest release (2026.09, 14 September 2026) updated indirect injection and LLM prompt obfuscation.

**Strengths and limitations.** Stable technique IDs and real case studies make it the best way to label test cases and incidents. It changes monthly, and the changelog itself contains a few inconsistent IDs, so the team should cite specific technique IDs with the release they were taken from.

**Relevance to Mirsad.** Each Mirsad red-team test case and each audit-log block reason can carry an ATLAS technique ID (for example AML.T0051.001 for an injected web page, AML.T0086 for an exfiltration attempt), which makes Mirsad's logs readable by a SOC that already uses ATT&CK-style tooling.

### [27] ISO/IEC 42001:2023: AI management system

**Reference.** *Information Technology — Artificial Intelligence — Management System*, ISO/IEC 42001:2023, 1st ed., ISO/IEC JTC 1/SC 42, Dec. 2023.

**Summary.** ISO/IEC 42001 specifies requirements and gives guidance for establishing, implementing, maintaining and continually improving an AI management system (AIMS) in any organization that provides or uses AI-based products or services. It was published on 18 December 2023 (51 pages) by the joint ISO/IEC committee on AI. Its aim is to help organizations develop, provide or use AI responsibly while meeting applicable requirements and stakeholder expectations. Public summaries describe an Annex A of reference controls (around 38) covering topics such as AI system impact assessment and the AI system lifecycle, applied through a statement of applicability; this detail could not be checked against the paywalled text.

**Strengths and limitations.** It is the first certifiable international management-system standard for AI and is becoming the reference for AI governance audits. It governs an organization's processes, not specific technical controls, and the text is not freely available.

**Relevance to Mirsad.** Mirsad cannot make an organization 42001-compliant on its own, but it can supply operational controls and evidence for an AIMS: documented tool policies, a record of human oversight decisions and a log of AI-system events.

### [28] ISO/IEC 27001:2022: information security management systems

**Reference.** *Information Security, Cybersecurity and Privacy Protection — Information Security Management Systems — Requirements*, ISO/IEC 27001:2022, 3rd ed., ISO/IEC JTC 1/SC 27, Oct. 2022 (amended by ISO/IEC 27001:2022/Amd 1:2024).

**Summary.** The standard sets requirements for establishing, implementing, maintaining and continually improving an information security management system, including assessing and treating information-security risks. The third edition was published on 25 October 2022 (19 pages) and replaced the 2013 edition; Amendment 1 (February 2024) added climate-action changes. An organization cannot claim conformity while excluding any requirement in clauses 4 to 10. Public summaries describe Annex A as 93 controls in four themes, including logging (8.15) and monitoring activities (8.16); these numbers come from secondary sources.

**Strengths and limitations.** It is the most widely certified security standard and a common procurement requirement in Saudi Arabia and elsewhere. It is technology-neutral and says nothing specific about LLMs.

**Relevance to Mirsad.** Mirsad's access-control policies, protected audit log and monitoring support the corresponding Annex A controls, letting an organization bring its AI agents inside an existing ISMS scope instead of treating them as an exception.

### [29] Model Context Protocol specification, version 2026-07-28

**Reference.** Model Context Protocol, "Specification," protocol revision 2026-07-28. [Online]. Available: https://modelcontextprotocol.io/specification/2026-07-28 (accessed Oct. 11, 2026).

**Summary.** MCP is an open JSON-RPC 2.0 protocol in which hosts (LLM applications) use clients to connect to servers that expose tools, resources and prompts; clients can offer elicitation back to servers. The current revision, 2026-07-28, is stateless (each request carries its protocol version and capabilities), while revisions up to 2025-11-25 used an initialization handshake. The specification's key security principles are user consent and control, data privacy and tool safety; the overview says descriptions of tool behavior such as annotations should be considered untrusted unless obtained from a trusted server, and the tools page makes this a MUST for clients. The tools page says there SHOULD always be a human able to deny tool calls, that clients SHOULD show tool inputs to the user before calling, validate tool results before passing them to the model and log tool usage for audit, and that servers MUST validate inputs, enforce access control, rate-limit and sanitize outputs; a separate security best-practices page covers confused-deputy attacks, token passthrough, SSRF, state-handle hijacking, local server compromise and scope minimization.

**Strengths and limitations.** It is the authoritative definition of the traffic Mirsad intercepts, and its normative security language gives Mirsad direct requirements to cite. The protocol says it cannot enforce these principles itself and leaves them to implementers, and its fast revision cycle means Mirsad must support at least two revisions.

**Relevance to Mirsad.** Mirsad is, in effect, an implementation of the MCP client-side SHOULDs that most hosts leave out: human-in-the-loop denial, showing arguments before a call, validating results before they reach the model, treating annotations as untrusted and logging for audit. The change to a stateless protocol also affects the design, because Mirsad's taint state must be keyed to the agent session it observes, not to an MCP connection.

---

## D. Saudi regulation and national strategy

### [30] NCA (2024): Essential Cybersecurity Controls (ECC-2:2024)

**Reference.** National Cybersecurity Authority, *Essential Cybersecurity Controls (ECC-2:2024)*, Riyadh, Saudi Arabia, 2024. [Online]. Available: https://cdn.nca.gov.sa/api/files/public/upload/86e09090-44e4-481f-bc28-355673607654_ECC--2024-EN.pdf

**Summary.** ECC-2:2024 replaces ECC-1:2018 and contains 4 main domains, 28 subdomains, 108 main controls and 92 subcontrols; the Arabic text is legally binding. It applies to government agencies and their affiliated entities and to private entities that own, operate or host critical national infrastructure, and the NCA encourages all other entities to use it. Relevant controls include 1-6-3 (secure coding, trusted sources for development libraries and secure integration between applications), 2-2-3 (authorization on need-to-know, least privilege and segregation of duties, privileged access management and MFA), 2-7 (data protection by classification level), 2-12-3 (event logging for critical assets and privileged accounts, continuous monitoring, SIEM, and at least 12 months of log retention), 2-13 (incident and threat management), 2-15 (web application security) and 4-1 (third-party cybersecurity).

**Strengths and limitations.** It is the baseline cybersecurity requirement for Mirsad's most likely Saudi adopters (government and CNI) and its controls are specific enough to map to features. It predates agentic AI and has no AI-specific controls, so mapping it to an LLM firewall requires interpretation.

**Relevance to Mirsad.** The 12-month retention and continuous-monitoring requirements of 2-12 directly shape Mirsad's audit-log design (retention policy, export to a SIEM), and 2-2-3's least privilege and segregation of duties map onto per-tool policy and human approval. Third-party MCP servers fall under 4-1, which supports Mirsad's treatment of tool descriptions and outputs as untrusted.

### [31] Kingdom of Saudi Arabia (2021, amended 2023): Personal Data Protection Law (PDPL)

**Reference.** Kingdom of Saudi Arabia, *Personal Data Protection Law*, Royal Decree No. M/19 of 9/2/1443H (16 Sep. 2021), Council of Ministers Resolution No. 98 of 7/2/1443H, amended by Royal Decree No. M/148 of 5/9/1444H (Mar. 2023). [Online]. Available: https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/b7cfae89-828e-4994-b167-adaa00e37188/1

**Summary.** The PDPL was issued in September 2021 and published in the Official Gazette on 24 September 2021; the 2023 amendment changed Article 43 so that the law took effect 720 days after publication, which places entry into force in mid-September 2023. It applies to processing of personal data in the Kingdom and to processing outside the Kingdom of data about residents. Article 19 requires controllers to take organizational, administrative and technical measures to protect personal data, including during transfer. Article 20 (as amended) requires controllers to notify the competent authority of a leak, damage or unlawful access, and to notify the data subject when it could harm them. Article 29 restricts transfers of personal data outside the Kingdom to defined purposes and conditions, and the issuing decree gave controllers one year from entry into force to adjust.

**Strengths and limitations.** The Bureau of Experts page shows the original and amended text of each article, which makes the citation precise. Most operational detail (notification deadlines, impact assessments) sits in the implementing regulations [32], which are being amended [33].

**Relevance to Mirsad.** An agent that reads a customer's email and then calls an external tool can leak personal data abroad in one step. Mirsad's taint tracking from untrusted inputs to external sinks, and its ability to block or escalate transfers to non-approved destinations, are technical measures under Article 19, and its tamper-evident log supports the breach investigation that Article 20 notification depends on.

### [32] SDAIA (2023): PDPL Implementing Regulation and Personal Data Transfer Regulation

**Reference.** Saudi Data and Artificial Intelligence Authority (SDAIA), *Implementing Regulation of the Personal Data Protection Law* and *Regulation on Personal Data Transfer outside the Kingdom*, Riyadh, Saudi Arabia, Sep. 2023. [Online]. Available: https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter

**Summary.** SDAIA published both regulations on 7 September 2023, a week before the PDPL took effect, and full enforcement followed the one-year grace period in September 2024 (dates confirmed through a Clyde & Co briefing; the SDAIA portal lists the documents without dates). The Implementing Regulation (Art. 24) requires controllers to notify SDAIA within 72 hours of becoming aware of a breach that could harm the personal data or the data subject, and to inform affected individuals without undue delay where the breach could harm them or conflict with their rights or interests. It also requires data protection impact assessments for higher-risk processing, records of processing activities, and responses to data-subject requests within 30 days. SDAIA's knowledge center adds guidelines on privacy policies, data minimization, anonymization, records of processing and transfer risk assessment.

**Strengths and limitations.** These are the operative rules that turn the law into concrete duties. Several provisions are under revision [33].

**Relevance to Mirsad.** The 72-hour window is the practical reason for Mirsad's real-time alerts and searchable, verifiable logs: a controller cannot assess a possible leak through an AI agent within three days without a trustworthy record of what the agent sent where.

### [33] Bajunaid and Ezzat (2026): SDAIA draft amendments to the PDPL Implementing Regulation

**Reference.** L. Bajunaid and N. Ezzat, "The SDAIA publishes draft amendments to the Implementing Regulations of the PDPL," Clyde & Co, Oct. 8, 2026. [Online]. Available: https://www.clydeco.com/en/insights/2026/10/sdaia-publishes-draft-amendments-to-the-pdpl

**Summary.** This law-firm briefing reports that SDAIA opened public consultation on draft amendments through the Istitlaa platform from 6 October to 5 November 2026. The draft would remove the harm threshold for notifying SDAIA, so any breach, damage or unauthorized access would have to be reported within 72 hours, while notification of individuals would stay harm-based. It would also require impact assessments for processing that involves emerging technologies and certain automated decisions, introduce a data-localization article, and require privacy policies in the language customarily used with the data subjects. Amendments would take effect 60 days after publication in the Official Gazette if adopted.

**Strengths and limitations.** It is the most current account of where Saudi data-protection rules are heading. It is a secondary source describing a draft that may still change.

**Relevance to Mirsad.** If adopted, a notify-on-any-breach rule raises the value of Mirsad's blocked-attempt records (which show that data did *not* leave), and an impact-assessment duty for emerging technologies would likely cover LLM agents. The language requirement reinforces the case for Arabic-first approval prompts in Mirsad's mobile app.

### [34] SDAIA: AI Ethics Principles

**Reference.** Saudi Data and Artificial Intelligence Authority (SDAIA), *AI Ethics Principles*, Doc. SDAIA-P114E, ver. 1, Riyadh, Saudi Arabia, May 2025 (English edition; the principles were adopted in Sep. 2023). [Online]. Available: https://sdaia.gov.sa/en/SDAIA/about/Documents/ai-principles.pdf

**Summary.** The framework applies to everyone who designs, develops, deploys, uses or is affected by AI systems in the Kingdom. It sets out seven principles: fairness; privacy and security; humanity; social and environmental benefits; reliability and safety; transparency and explainability; and accountability and responsibility. It defines four risk levels (little or no risk, limited, high and unacceptable), requiring pre- and post-deployment conformity assessments for high-risk systems and prohibiting unacceptable ones, and it maps controls onto a four-stage lifecycle (plan and design, prepare input data, build and validate, deploy and monitor). The principles were adopted on 14 September 2023 according to Digital Policy Alert; the English PDF now on SDAIA's site is dated May 2025.

**Strengths and limitations.** It is the national ethical reference that a Saudi AI project is expected to cite and includes a practical risk classification. It is guidance with general controls rather than technical security requirements.

**Relevance to Mirsad.** Mirsad supports the privacy-and-security, reliability-and-safety and accountability principles in the deploy-and-monitor stage. Measuring the detector's error rates separately for Arabic dialects and English [6]–[8] supports the fairness principle, because a firewall that blocks Arabic users more often would itself be unfair.

### [35] SDAIA: Generative Artificial Intelligence Guidelines for Government

**Reference.** Saudi Data and Artificial Intelligence Authority (SDAIA), *Generative Artificial Intelligence Guidelines for Government*, Doc. SDAIA-P116E, ver. 1, Riyadh, Saudi Arabia, May 2025 (English edition; first released Jan. 2024). [Online]. Available: https://sdaia.gov.sa/en/SDAIA/about/Files/GenAIGuidelinesForGovernmentENCompressed.pdf

**Summary.** The guidelines tell government entities how to use generative AI tools and process government data responsibly, and require them to follow the AI Ethics Principles across the tool lifecycle. They state that all generative-AI results should be reviewed by a human and that generative AI should not be used in critical decisions affecting individuals or the Kingdom's vital interests. Employees must not enter data classified as restricted or higher, use of the tools should be limited to public-classified data, and tools must respect PDPL requirements and NCA cybersecurity standards. Data leakage, misinformation and deepfakes are listed among the main risks, and an appendix gives a usage checklist. The guidance was first reported publicly in January 2024 (Arab News, 12 January 2024); the English PDF now on SDAIA's site is dated May 2025.

**Strengths and limitations.** It is the most specific Saudi document on generative AI in government and directly addresses data classification and human review. It is written for chat-style use by employees and does not discuss autonomous agents or tool calling.

**Relevance to Mirsad.** Mirsad turns these written rules into enforcement for agents: classification-aware taint labels can stop restricted data from reaching external tools, and the mobile approval flow implements the human review the guidelines ask for, for the subset of actions that matter most.

### [36] Kingdom of Saudi Arabia (2016): Saudi Vision 2030

**Reference.** Kingdom of Saudi Arabia, *Saudi Vision 2030*, Riyadh, Saudi Arabia, Apr. 2016. [Online]. Available: https://www.vision2030.gov.sa/media/rc0b5oy1/saudi_vision203.pdf

**Summary.** Vision 2030, approved by the Council of Ministers in April 2016, is built on three themes: a vibrant society, a thriving economy and an ambitious nation. Under "an ambitious nation" it commits to effective e-government, including expanding online services, wider use of cloud applications and data-sharing platforms in government, and stronger governance of online services, with a target to rise from 36th place to the top five in the UN E-Government Survey. Under "a thriving economy" it commits to a developed digital infrastructure and to governing digital transformation through a national council. The National Transformation Program, approved in June 2016, is one of the programs that implement these goals.

**Strengths and limitations.** It is the policy anchor for any Saudi senior project and explains why government adoption of AI agents is expected to grow. It is a strategy document with no technical requirements, and it predates generative AI.

**Relevance to Mirsad.** As government services become more automated, AI agents will handle citizen and government data, and Mirsad is a local, Arabic-capable control that lets that automation happen within NCA, PDPL and SDAIA rules. This is the national-relevance argument for the project.

---

## Synthesis

### Themes

**1. Safety does not transfer evenly across languages, scripts and dialects.** Model-level safety degrades as the input moves away from the language and form it was trained on: low-resource languages [1], [2], transliteration and Arabizi [3], and regional dialects, where [7] reports degradation consistent with distance from MSA and [6] finds the effect strongly model-dependent. Arabic is not uniformly "unsafe" (MSA had a low bypass rate in [1] and Arabic injections had little effect in [11]), but the less standard forms of Arabic that Saudi users actually write are where defenses fail. NIST [25] and OWASP LLM01 [21] both list language-switching and obfuscation as standard techniques, and ASAS [9] found obfuscation attacks the most effective in Arabic.

**2. Arabic safety benchmarks have matured quickly, but they measure harmful requests, not injected instructions.** Between 2025 and 2026 the community produced culturally grounded sets [4], native-prompt sets [5], dialect-annotated sets [6], [8] (only [6] has a Saudi split), a human-scored red-team set [9] and a shared task [10]. All of them ask whether a model answers, or a classifier flags, a harmful *request*. None of them is a benchmark of instructions hidden in tool outputs that hijack an agent.

**3. Small fine-tuned Arabic encoders are competitive classifiers.** MARBERTv2 beat prompted frontier LLMs on Arabic dialect safety classification [8], top ArGuard systems reached 0.98 macro-F1 on binary harmful-prompt detection [10], and CAMeLBERT's results show that matching the pretraining variant to the target text matters more than model size [16]. A hybrid of a small Qwen2.5 classifier and lexical features worked well for multilingual indirect injection [13]. This supports a compact detector in Mirsad's request path, with LLM judging, if used at all, kept out of it.

**4. Every major framework now says the same things about agents: least privilege, complete mediation, separation of untrusted content, human approval and logging.** OWASP LLM01 and LLM06 [21], the OWASP agentic list [23], NIST AI 100-2's advice to design as if injection will happen [25] and the MCP specification's security sections [29] converge on the same controls. The MCP specification goes further and writes them as SHOULD and MUST requirements for clients and servers, but it also says the protocol cannot enforce them; enforcement is left to implementers.

**5. Saudi rules require the evidence that a firewall produces.** ECC-2:2024 requires least privilege, segregation of duties, continuous monitoring and 12 months of log retention [30]. The PDPL requires technical protection measures and breach notification [31], and the regulations set a 72-hour window [32] that the October 2026 draft would extend to every breach regardless of harm [33]. SDAIA's guidance requires human review of generative-AI output and keeps restricted data out of these tools [35]. None of these documents mentions AI agents or tool calls, so an organization deploying agents has to translate them into technical controls itself.

### Gaps that Mirsad addresses

| Gap in the literature or practice | Evidence | How Mirsad addresses it |
|---|---|---|
| No public benchmark or detector for **Arabic indirect prompt injection** against tool-using agents | Arabic sets cover harmful requests [4]–[10]; multilingual IPI defenses skip Arabic [13]; Prompt Guard 2 lists no Arabic [14]; the only IPI study found in this review that includes Arabic covers a single task [11] | Bilingual Arabic/English injection detector trained and evaluated on tool-output-style text, including Gulf dialect and Arabizi; the team's test set can be released as a contribution |
| Script and dialect evasion defeats learned filters | [3], [6]–[9] | Text normalization before classification, plus deterministic policy and taint controls that do not depend on the classifier |
| Arabic sessions produce more tool-call errors | 5-10% accuracy drop in Arabic [12] | Per-parameter schema and value policies catch malformed or out-of-policy arguments, whatever their cause |
| MCP security requirements are left to implementers | MCP spec says the protocol cannot enforce its principles [29] | A drop-in gateway that implements human-in-the-loop denial, argument display, result validation, untrusted annotations and audit logging for any MCP or function-calling agent |
| Saudi regulations are written for people and organizations, not agents | [30]–[35] contain no agent-specific controls | Mapping of each regulatory control to an enforceable Mirsad policy or log record (table below) |
| Detector fairness across dialects is rarely measured | Dialect Safety Gap metrics [7] | Report detector false-positive and false-negative rates per dialect and language, in line with SDAIA's fairness principle [34] |

### Mapping of standards and regulations to Mirsad features

Feature key: **P** = declarative per-tool / per-parameter policy engine; **T** = taint tracking of untrusted content to external sinks; **D** = Arabic/English injection detector; **H** = human-in-the-loop approval via mobile web app; **A** = tamper-evident hash-chained audit log. Mirsad supports compliance; it does not by itself make an organization compliant.

| Standard / regulation | Relevant provision | Mirsad features | How Mirsad supports it (evidence it can produce) |
|---|---|---|---|
| OWASP Top 10 for LLM Apps 2025 [21] | LLM01 Prompt Injection | D, T, P, H | Detector flags injected instructions (including multilingual or obfuscated); taint labels separate untrusted content; risky calls go to human approval |
| | LLM06 Excessive Agency | P, H, A | Tool and parameter allow-lists (minimal functionality and permissions), complete mediation of every call, approval for high-impact actions, activity logging |
| | LLM02 Sensitive Information Disclosure | T, P | Blocks or escalates flows of tainted or sensitive data to external sinks |
| OWASP Agentic Top 10 for 2026 [23] and ASI Threats & Mitigations [22] | ASI01 Goal Hijack; ASI02 Tool Misuse and Exploitation; ASI03 Identity & Privilege Abuse; ASI04 Supply Chain; ASI09 Human-Agent Trust Exploitation | D, T, P, H, A | Detection and taint for hijack; per-tool policy for misuse and privilege; tool descriptions treated as untrusted; approval screens show raw arguments and taint provenance instead of the agent's own summary |
| NIST AI RMF 1.0 [24] | Govern / Map / Measure / Manage; "secure and resilient," "accountable and transparent" | P, A, D | Versioned policies as governance artifacts (Govern); detector metrics and block statistics (Measure); runtime enforcement (Manage); audit trail for accountability |
| NIST AI 100-2e2025 [25] | §3.4 indirect prompt injection mitigations; §3.5 agent security | T, D, P | Implements detection, separation of untrusted data and "well-defined interfaces" to untrusted sources; uses NIST terminology in the threat model |
| MITRE ATLAS [26] | AML.T0051 (.000/.001/.002), AML.T0053, AML.T0086 | D, T, A | Red-team cases and log entries tagged with ATLAS technique IDs for SOC correlation |
| ISO/IEC 42001:2023 [27] | AI management system: risk treatment, operational control, monitoring, human oversight (Annex A per public summaries) | P, H, A | Documented, reviewable AI tool policies; records of human oversight decisions; AI-system event logs as audit evidence |
| ISO/IEC 27001:2022 [28] | Access control; logging (8.15) and monitoring (8.16) per public summaries | P, A | Least-privilege enforcement for agents; protected, tamper-evident logs; alert feed for monitoring |
| MCP specification 2026-07-28 [29] | Tools: human in the loop, show inputs, validate results, log for audit; annotations untrusted; security best practices | H, P, T, A | Sits between MCP client and server to provide the client-side controls hosts often omit |
| NCA ECC-2:2024 [30] | 2-2-3 least privilege, need-to-know, segregation of duties, PAM | P, H | Per-tool and per-parameter authorization; human approver separate from the agent for privileged actions |
| | 2-12-3 event logging, continuous monitoring, SIEM, ≥12-month retention | A | Hash-chained logs with configurable retention of at least 12 months and SIEM export |
| | 2-7 data protection by classification; 4-1 third-party cybersecurity; 1-6-3 secure integration | T, P | Classification-aware taint labels; third-party MCP servers treated as untrusted; policy-checked integration |
| | 2-13 incident and threat management | A, D | Detector alerts and verifiable logs feed incident handling |
| Saudi PDPL [31] | Art. 19 technical and organizational protection measures, including during transfer | T, P | Blocks or escalates personal data flowing from untrusted context to external or foreign destinations |
| | Art. 20 breach notification | A | Verifiable record of what data reached which tool, supporting scoping of an incident |
| | Art. 29 transfers outside the Kingdom | P, T | Destination allow-lists for outbound tools (e.g., only in-Kingdom endpoints) |
| PDPL Implementing Regulation [32] and Oct. 2026 draft amendments [33] | 72-hour notification; DPIA; records of processing; proposed DPIA for emerging tech; privacy notices in the subjects' language | A, H, D | Fast, searchable evidence for 72-hour assessment; logs that support impact assessments; Arabic-first approval prompts |
| SDAIA AI Ethics Principles [34] | Privacy & security; reliability & safety; transparency; accountability; fairness | P, T, A, D | Runtime safeguards in the deploy-and-monitor stage; traceable decisions; per-dialect detector error rates as a fairness measure |
| SDAIA GenAI Guidelines for Government [35] | Human review of outputs; no restricted data in GenAI tools; NCA and PDPL compliance | H, T, P | Approval flow for consequential actions; taint and classification labels keep restricted data out of external tools |
| Saudi Vision 2030 [36] | Effective e-government; governance of digital transformation | All | A locally built, Arabic-capable control that lets government agencies adopt AI agents within national rules |

### Recommendations for the project report

1. Cite [21], [23], [25] and [29] together when stating the problem: the three framework families (OWASP, NIST, MCP) agree on the mitigations, and Mirsad implements them at one enforcement point.
2. Build the detector evaluation around per-language and per-dialect results (MSA, Gulf/Saudi, Arabizi, English, code-switched), using MultiJail-ar [2], AraSafe [5] and the SalamahBench Saudi split [6] for the benign and harmful-request sides, and a team-built Arabic indirect-injection set for the attack side, with attack categories kept disjoint between training and test as in [13].
3. Start with MARBERTv2 [17], CAMeLBERT-DA/Mix [16], XLM-R [18] and a small Qwen2.5 [19] as backbone candidates and compare against Prompt Guard 2 [14] on English.
4. Set the audit-log retention default to at least 12 months and provide SIEM export to match ECC-2:2024 2-12-3 [30]; tag log entries with ATLAS technique IDs [26].
5. Track the PDPL draft amendments [33] until the consultation closes on 5 November 2026, and revise the compliance chapter if the notify-on-any-breach rule is adopted.

---

## Verification log

*Independent fact-check, 11 October 2026. Every reference was re-opened on its original or official source: arXiv abstract pages, the arXiv API (versions, comments, journal-ref) and the full PDFs; ACL Anthology pages and PDFs; Hugging Face model cards; genai.owasp.org resource pages and the official OWASP PDFs; nist.gov, csrc.nist.gov and the NIST PDFs; the mitre-atlas/atlas-data CHANGELOG on GitHub; IEC webstore records; modelcontextprotocol.io; the NCA PDF; laws.boe.gov.sa (Arabic text; the site's TLS chain did not validate, so it was fetched without certificate checking, read-only); the SDAIA data-governance portal and SDAIA PDFs; the Vision 2030 PDF; Clyde & Co; Digital Policy Alert; Arab News; Argaam; and ARY News (AFP).*

### Confirmed without change

- **[1]** Authors, title, SoLaR 2023 and the Best Paper Award (arXiv comments). The full text confirms 520 AdvBench behaviors, the Google Translate API, 12 translated languages, 79.04% combined low-resource BYPASS, and MSA in the high-resource group at 3.65%.
- **[2]** ICLR 2024 (arXiv comments). The PDF confirms 315 prompts translated by native speakers into 9 languages, Arabic as medium-resource, unsafe rates of 80.92% (ChatGPT) and 40.71% (GPT-4), the roughly 3x low- vs high-resource gap for both models, and Self-Defense fine-tuning of ChatGPT.
- **[3]** ACL Anthology metadata (EMNLP 2024, Miami, Nov. 2024, pp. 18584–18600, DOI). The PDF confirms GPT-4 and Claude 3 Sonnet, that prefix injection in standard Arabic was insufficient, and that the chatspeak mapping uses digits such as 3 and 7.
- **[4]** ACL Anthology metadata and PDF: 1,024 region-specific direct-attack questions, 5,799 in total, adapted from a Chinese dataset, dual-perspective evaluation, five LLMs.
- **[5]** ACL Anthology metadata and PDF: about 12K native prompts, independent double annotation into nine categories, 12K GPT-4o synthetic harmful prompts, 7–13B models, BERT classifiers, GPT-4o upper bound.
- **[6]** arXiv metadata (v3, 29 Sep 2026) and PDF: 8,270 prompts, MSA plus five varieties including Saudi, 49,620 items, the two metrics, Fanar 2, ALLaM 2 and Karnak 1.
- **[7]** ACL Anthology: TrustNLP 2026 (6th workshop), Jul. 2026, San Diego, pp. 503–514, DOI. The PDF confirms DSG, PDI and DASEP and the five-variety probe.
- **[9]** arXiv metadata (Aug. 2026, authors) and PDF: 801 prompts, 8 categories, 8 attack types, seven models, 4-point human scale, poor GPT-4o judge agreement. The PDF running header says "Published at the MELT Workshop, COLM 2025"; no official venue page confirming this was found, so the reference keeps the arXiv citation.
- **[10]** arXiv metadata (Sep. 2026, eight authors) and PDF: 58 registered and 35 participating teams, best B1 0.984 and B2 0.790, the label-mapping caveat, and controlled access to the Task B data.
- **[11]** arXiv metadata and abstract: about 500 ICML papers, four languages, little or no effect from Arabic injections.
- **[12]** arXiv metadata: LLMs4All workshop at IEEE BigData 2025, Macau, 10 Dec. 2025; 5–10% average drop regardless of tool-description language.
- **[13]** arXiv metadata and abstract: XLPID (Qwen2.5-1.5B with LoRA), over 1.43M BIPIA-derived samples, disjoint attack categories, TF-IDF+SVM F1 0.77, hybrid F1 0.9205, boosting AUROC 0.9378, English and Bangla only.
- **[15]–[18]** ACL Anthology metadata (venues, months, locations, pages, DOIs) and abstracts. The CAMeLBERT PDF confirms 167 GB / 17.3B words for the Mix model. The ARBERT & MARBERT paper itself reports MARBERT-v2.
- **[19]** arXiv v2 (Jan. 2025) and PDF: 7T to 18T tokens, over 1M SFT examples, multistage RL, AMMLU 72.44 (72B-Instruct) and 59.78 (7B-Instruct), MGSM8K extended to Arabic. **[20]** Hugging Face card: 29+ languages including Arabic, 131,072-token context, structured/JSON output.
- **[21]** OWASP resource page dated 17 Nov 2024. The LLM Top 10 list confirms LLM07 System Prompt Leakage and LLM08 Vector and Embedding Weaknesses, and LLM01 scenario #9 is a multilingual/obfuscated attack.
- **[23]** OWASP resource page (9 Dec 2025, "more than 100 industry experts") and the official PDF for the ASI01–ASI10 names.
- **[24]** nist.gov publication record (author Elham Tabassi, 26 Jan 2023, DOI). The AI RMF page confirms AI 600-1 (26 Jul 2024) and states that "the AI RMF 1.0 is being revised as part of the White House AI Action Plan". The PDF lists the seven characteristics.
- **[25]** CSRC record (March 2025, six authors in order, DOI); no newer edition was found. The PDF confirms §3.4 (resource control; availability, integrity and privacy), the §3.4.4 mitigations (hierarchical-trust training, detection, filtering, spotlighting, multiple LLMs with different permissions, well-defined interfaces), §3.5 on agent hijacking and exfiltration, and translation into a less common language as a jailbreak technique.
- **[26]** The atlas-data CHANGELOG confirms 2026.09 (14 Sep 2026; updates to LLM Prompt Injection: Indirect and LLM Prompt Obfuscation), 2026.08 agent mitigations (AI Agent Authority Expansion Controls, Scope Drift Detection), the 5.5.0 release of 30 Mar 2026 with the two poisoned-MCP case studies, the AML.T0051.000/.001/.002, AML.T0053 and AML.T0086 names, and the inconsistent IDs ("AML.T086"; AI Agent Tool Poisoning listed as both T0108 and T0110).
- **[27]** IEC webstore: 2023-12-18, ed. 1.0, 51 pages, JTC 1/SC 42. **[28]** IEC webstore: 2022-10-25, ed. 3.0, 19 pages, JTC 1/SC 27, the clauses 4–10 exclusion rule, and Amd 1:2024 "Climate action changes" (2024-02-23). Both Annex A descriptions (about 38 controls; 93 controls in four themes, 8.15/8.16) still rest only on secondary summaries, as already flagged in the text.
- **[29]** modelcontextprotocol.io: 2026-07-28 is the "current" revision; stateless, self-contained requests; handshake-based revisions are 2025-11-25 and earlier; elicitation is the only client feature listed. The tools page has the human-in-the-loop SHOULD, the client SHOULDs and the server MUSTs. The security best-practices page covers confused deputy, token passthrough, SSRF, state-handle hijacking, local server compromise and scope minimization, among others.
- **[30]** NCA PDF: replaces ECC-1:2018; 4 domains, 28 subdomains, 108 main controls and 92 subcontrols; Arabic version binding; scope as stated; 1-6-3, 2-2-3 (need-to-know, least privilege, segregation of duties, PAM, MFA), 2-7, 2-12-3 (≥12 months log retention, SIEM, continuous monitoring), 2-13, 2-15, 4-1.
- **[31]** Bureau of Experts Arabic text: M/19 of 9/2/1443H (16 Sep 2021), CoM Resolution 98 of 7/2/1443H, published 17/2/1443H (24 Sep 2021). M/148 of 5/9/1444H amended Art. 43 from 180 to 720 days (giving 14 Sep 2023). Arts. 2, 19, 20 (as amended) and 29 (as amended) match the summary, as does the decree's one-year adjustment period (clause Third).
- **[32]** The SDAIA portal text of the Implementing Regulation confirms Art. 24 (72 h), Art. 25 (impact assessment), Art. 33 (records) and Art. 3 (30 days). The Clyde & Co note of 8 Sep 2023 confirms publication on 7 Sep 2023 and full enforcement from 14 Sep 2024.
- **[33]** Clyde & Co page: title, 8 Oct 2026, authors, Istitlaa consultation 6 Oct to 5 Nov 2026, removal of the harm threshold, new DPIA triggers, a localisation article, the privacy-policy language rule, and entry into force 60 days after gazetting.
- **[34]** SDAIA PDF: SDAIA-P114E, ver. 1, May 2025, the seven principles, four risk levels and the lifecycle stages. Digital Policy Alert gives adoption on 14 Sep 2023.
- **[35]** SDAIA PDF: SDAIA-P116E, ver. 1, May 2025, human review, the ban on critical decisions, restricted-or-higher data excluded, public data only, PDPL and NCA references, the listed risks and the checklist appendix. The Arab News article is dated 12 Jan 2024.
- **[36]** Vision 2030 PDF: three themes, e-government text (ranked 36th; target of the top five), cloud and data-sharing platforms, digital infrastructure and the national council. Cabinet approval on 25 Apr 2016 (Argaam) and NTP approval in June 2016 (AFP via ARY News, 7 Jun 2016); the vision2030.gov.sa program page served a bot challenge and could not be read.

### Corrected

- **[2]** "the most cited peer-reviewed study in this area" changed to "a widely cited peer-reviewed reference" (the superlative could not be verified).
- **[3]** Added that the Arabic translation was made with GPT-3.5 Turbo and proofread. Changed "common in real Gulf online writing" (not in the paper) to the paper's own claim that young Arabic speakers widely use chatspeak.
- **[4]** Added the month (Apr. 2025) from the ACL Anthology.
- **[7]** Stated the probe size (20 base prompts × 5 varieties) and quoted the paper's actual finding (endpoints consistent with distance from MSA).
- **[8]** The prompt count was given as 25,071. That is the arXiv abstract figure, but the current PDF's abstract and dataset table give 24,051, so both figures are now reported. The data-release wording was updated.
- **[9]** "the abstract does not say whether prompt injection is one of the eight strategies" replaced with the paper's actual list of eight attack types, none of which is prompt injection.
- **[10]** "held-out AraSafe prompts" made precise: 5,981 AraSafe test-set prompts, and train/dev data drawn only from ArabicDialectSafety.
- **[14]** The 512-token window is in the card's model-scope section, not its limitations list. Wording corrected.
- **[17]** Added the location (Online).
- **[21]** "states that no known method fully prevents injection" corrected to the page's actual wording (it is "unclear if there are fool-proof methods of prevention"). LLM01 and LLM06 mitigation lists aligned with the official headings; logging is listed in LLM06 as damage limitation, not prevention.
- **[22]** The resource now distributes **ver. 1.1 (Dec. 2025)**, not ver. 1.0, and the reference was updated. The claim that its numbering "was superseded" by [23] was wrong: [23] maps each entry to this guide's T-numbered threats and calls it OWASP's "foundational and detailed taxonomy". The text was rewritten to match.
- **[23]** Official names corrected: ASI02 is "Tool Misuse and Exploitation" and ASI05 is "Unexpected Code Execution (RCE)" (also changed in the mapping table).
- **[29]** The spec overview says annotations "should be considered untrusted"; the MUST comes from the tools page. Wording corrected.
- **[32]** The Art. 24 notification duties are now stated with their harm conditions.
- **Synthesis, Theme 1.** [6] does not show degradation increasing with distance from MSA; it finds robustness strongly model-dependent. The sentence now attributes the distance pattern to [7] only.
- **Synthesis, Theme 2.** "dialect-paired sets including Saudi dialect [6], [8]" implied that [8] has a Saudi split, which it does not. Corrected.
- **Gaps table.** "only one IPI study includes Arabic" narrowed to "the only IPI study found in this review", because an exhaustive negative could not be verified.

### Removed

- No reference had to be removed. Every one of the 36 entries was found on its original or official source with matching authors, title, venue and date, after the corrections above.
