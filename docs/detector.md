# Injection Detector (كاشف حقن التعليمات) — `mirsad.detector`

| | |
|---|---|
| **Owner** | Abdullah Naif Al-Orabi |
| **Specification** | `docs/dev/BUILD_SPEC.md`, sections 4 and 12 |
| **Code** | `src/mirsad/detector/` (`normalize.py`, `language.py`, `rules.py` + `rules/*.yaml`, `model.py`, `detector.py`, `sanitize.py`, `dataset.py`, `build_dataset.py`, `augment.py`, `train.py`, `metrics.py`, `figures.py`) |
| **Tests** | `tests/detector/` (227 tests, no adversarial text) |
| **Used by** | `mirsad.gateway` (`inspect_result`), `POST /api/detector/scan`, `mirsad scan`, Mirsad-Bench |

## 1. Purpose

Tool results such as e-mails, web pages, documents and CRM notes are written by people the
agent's user does not control. An *indirect prompt injection* hides text in that content that
is addressed to the AI agent rather than to the human reader. The text tries to change what the
agent does: it may try to make the agent forget its task, send data somewhere, or call a tool the
user never asked for [1], [2].

The detector is the layer of Mirsad that reads this content. For every result of a tool marked
`trust: untrusted` (or `scan: true`) the gateway asks the detector for a **score in [0, 1]**,
the **spans** that caused it and the **evasion signals** it saw. It then acts on the result,
following the tool's `detector:` policy settings:

* **pass**: the score is below the flag threshold;
* **flag**: the result is passed through, labelled and audited, and the session is marked;
* **sanitize**: the suspected instructions are cut out and replaced with a visible bilingual marker;
* **block**: the whole result is withheld and replaced with a bilingual notice.

The result may also be **spotlighted**, which means it is wrapped in data markers that tell the
model to treat it as data [3].

The detector is a *signal*, not a security boundary. Every classifier in the team's literature
review that was tested against adaptive attackers was bypassed [4], [5]. This is why Mirsad does not rely
on it alone. The policy engine and the taint tracker (`docs/taint-tracking.md`) block the
harmful *actions* even when the detector misses the text. The detector's job is to catch the
common cases cheaply and to feed the `TAINT_AFTER_INJECTION` rule. It also gives approvers and
auditors evidence they can read.

## 2. Pipeline

```
 text ──► normalize() ──► NormalizedText(text, signals, offsets)
              │                     │
              │            ┌────────┴─────────┐
              │            ▼                  ▼
              │     RuleSet.match()     LinearTextModel.score_windows()
              │     weighted regex      hashed char+word n-grams → logistic regression
              │     rule_score r        max window probability m
              │            └────────┬─────────┘
              │                     ▼
              │      noisy-OR  raw = 1 − (1−m)^α · (1−r)^β ;  score = calibrate(raw, pivot)
              ▼                     ▼
      detect_language()     DetectionResult(score, label, language, spans, signals,
                                            model_score, rule_score, latency_ms)
                                    │
                    gateway: pass / flag / sanitize() / block  (+ spotlight())
```

`InjectionDetector.default()` loads the packaged model from `src/mirsad/detector/model/`. If
that directory is missing, empty or invalid (wrong shape, non-finite weights, an object array, a
corrupt `meta.json`), the detector logs the reason and runs in **rules-only mode**. In that mode
the score is just the rule score, so the gateway never fails because of a missing or damaged
model. `detector.mode` reports `"ensemble"` or `"rules_only"`. `detector.version` is a
fingerprint of the rule base and the model weights (`rules-<hash>[+model-<hash>]`). Audit
replays include it so that a changed score can be traced to a changed detector.

## 3. Normalisation (`normalize.py`)

Attackers disguise instructions so that they look different to keyword matchers and classifiers
but read the same to a language model. Character-level tricks are among the most effective
evasions against deployed detectors [4]. `normalize(text)` produces one canonical view.

| Step | What happens | Signal raised |
|---|---|---|
| HTML entities | Named and numeric entities are decoded. An entity counts as one unit in the offset map. | `html_entities` (≥ 3 letters written as numeric entities) |
| Invisible characters | Zero-width space/joiner/non-joiner, word joiner, soft hyphen, BOM and similar characters are removed. A leading BOM, a ZWNJ between Arabic-script letters (Persian/Urdu spelling) and a ZWJ inside emoji are kept as legitimate. | `zero_width_chars` |
| Bidi controls | Embedding, override and isolate controls (LRE, RLE, PDF, LRO, RLO, LRI, RLI, FSI, PDI) are removed. The direction marks LRM, RLM and ALM are routine in Arabic, so they are removed without a signal. | `bidi_controls` |
| NFKC | Compatibility forms (fullwidth, mathematical alphanumerics, ligatures, enclosed letters) are folded. | `compat_chars` (≥ 3) |
| Case | Text is lower-cased. | – |
| Diacritics | Arabic tashkeel and Quranic marks are removed. Latin combining accents are removed. | `tashkeel_obfuscation` when marks are stacked, repeated or detached from a letter; `combining_marks` (≥ 3) |
| Tatweel | The elongation character is removed. | `arabic_elongation` (≥ 3) |
| Arabic letters | Alef variants become ا, alef maqsura becomes ي, ta marbuta becomes ه, hamza carriers become plain letters, and Persian/Urdu look-alikes (keheh, Farsi yeh, heh forms, dotless forms) become their Arabic letters. | – |
| Digits | Every Unicode decimal digit (Arabic-Indic, Extended Arabic-Indic, fullwidth, …) becomes ASCII. | – |
| Homoglyphs | Cyrillic, Greek and Armenian look-alikes are folded to Latin, but only inside words that contain Latin letters or in Latin-dominant text, so real Russian or Greek is left alone. Dotless i and small-capital letters are folded too. | `homoglyphs`, `mixed_scripts` |
| Letter spacing | Words written as single letters separated by spaces, dots or dashes are joined. | `letter_spacing` (runs of ≥ 5 letters) |
| Whitespace | Runs of whitespace collapse to one space, or to a newline if the run contained one, so line-anchored rules keep working. | – |
| Structural | No change to the text; the detector only looks for patterns. | `base64_blob`, `html_hidden_text`, `markdown_image_url` |

**Offset map.** `NormalizedText.offsets[i]` is the index in the original string of normalised
character `i`. `to_original(start, end)` maps a normalised span back to the smallest original
span that contains it. That span includes an entity's full source text and any marks or
invisible characters removed right after the last character. Spans reported to the gateway,
the dashboard and `sanitize()` therefore always point at the text that the user and the model
actually see, even when that text was full of invisible characters.

The *evasion* signals (zero-width, bidi, homoglyphs, mixed scripts, tashkeel, elongation,
combining marks, compatibility characters, letter spacing, entities) do not raise the score on
their own. Ordinary Arabic and multilingual text produces some of them. They amplify the score
only when a rule has also fired (section 5.3).

## 4. Language identification (`language.py`)

`detect_language(text)` returns `en`, `ar`, `mixed` or `other`. It is used for reporting and
for per-language evaluation; it never changes the score. E-mail addresses and URLs are removed
first, because they are Latin even inside Arabic text. The decision uses the share of Arabic
letters among Arabic and Latin letters: ≥ 0.7 is `ar`, > 0.3 is `mixed`. Mostly Latin text is
checked for Arabizi, which is Latin script with digits standing for Arabic sounds. A high share
of Arabizi tokens gives `ar`, and a moderate share gives `mixed`. Short technical tokens such as
`b2b` or `4g` are excluded. When letters from other scripts dominate, the result is `other`.

## 5. Rule layer (`rules.py`, `rules/*.yaml`)

### 5.1 Format

Rules are YAML so that reviewers can read and extend them without touching code. Each rule has:

| Field | Meaning |
|---|---|
| `id` | Dotted identifier, e.g. `en.ctx.…`, `ar.addr.…`, `struct.hidden.…` |
| `category` | One of: context_ignoring, role_impersonation, addressing_ai, action_directive, exfiltration, secrecy, urgency_authority, tool_knowledge, prompt_leak, jailbreak, hidden_content, payload_splitting, obfuscation, goal_hijack |
| `weight` | (0, 1), the rule's contribution to the score |
| `lang` | en / ar / arabizi / any |
| `pattern` | Python regex over the *normalised* text. `{{MACRO}}` placeholders are expanded from `macros.yaml`. Arabic in a pattern is folded at load time, so authors can write natural spelling. |
| `triggers` | Optional substrings. The regex runs only if one of them occurs, which is a cheap pre-filter. |
| `guard` | Optional regex that the matched text must also contain |
| `signal` | Optional signal name added to the result when the rule fires |
| `examples` / `negatives` | Texts the rule must / must not match. These are maintained by the rule authors. |

The packaged rule base has 158 rules:

* 76 English (`en.yaml`);
* 51 Arabic (`ar.yaml`): MSA and Gulf, with some Egyptian and Levantine forms;
* 7 Arabizi (`arabizi.yaml`);
* 24 language-independent rules (`structural.yaml`): 20 structural rules covering
  chat-template tokens, hidden HTML/CSS, markdown-image exfiltration and payload splitting,
  plus 4 obfuscation rules.

Weights range from 0.10 to 0.80 (median 0.45). Following the rule files' own convention,
weights of about 0.7–0.85 mean near-certain injection phrasing and 0.4–0.6 a strong cue.
Weights of 0.3 or less mark weak cues that matter only in combination, because benign business
text is full of imperatives such as customer requests to send something somewhere.

### 5.2 Matching

`RuleSet.match(normalized)` returns `RuleHit`s with normalised and original spans. A rule
counts at most 25 hits. When the text contains a base64 blob, each blob is decoded one level
and the rules are run on the decoded text. If anything fires, an `obf.base64_payload` hit
covers the blob. Hits that appear *inside quotation marks* in text that discusses attacks (a
security article, training material) have their weight halved. This damping reduces false
positives on descriptive content without letting unquoted instructions through.

### 5.3 Rule score

```
r = 1 − Π_rules (1 − w_rule) · Π_evasion (1 − 0.1)      capped at 0.99
```

The product runs over *distinct* rules that fired, taking the best weight per rule, so
repeating one phrase does not raise the score. Up to three distinct evasion signals each
multiply the remaining probability by 0.9, but only when at least one rule fired.

## 6. ML model (`model.py`)

### 6.1 Features and classifier

The model reads the normalised text, so obfuscation is already removed. It uses two hashed
feature blocks:

* **character n-grams** (2–5, `char_wb`, i.e. within word boundaries) hashed into 2^20 columns;
* **word n-grams** (1–2, token pattern `\b\w+\b`) hashed into 2^18 columns.

Each block is L2-normalised separately and the blocks are concatenated. The classifier is a
class-balanced logistic regression (liblinear). C is chosen from a small grid by validation
PR-AUC.

### 6.2 Sliding windows

An injection can be one sentence inside a long e-mail. If the whole text were scored as one
bag of n-grams, that sentence would be diluted. The text is therefore cut at whitespace into
chunks of about `stride_chars` (default 300) and each chunk is featurised **once**. A window
(default 600 characters) is the sum of consecutive chunk vectors, re-normalised. The model score
is the **maximum window probability**. Windows that score at or above the tuned
`model_threshold` become `model:window` spans (at most 3) so that `sanitize()` can remove them.

### 6.3 Persistence without pickle

Loading a pickled scikit-learn object can execute arbitrary code. A model file is an artefact
that people pass around, so it is also an attack surface. The trained model is therefore saved
as plain data only:

| File | Content |
|---|---|
| `coef.npy` | float32 weight vector (1,310,720 values, about 5 MB) |
| `intercept.npy` | one float64 |
| `meta.json` | format version, feature configuration, ensemble configuration (α, β, pivot, thresholds), training metadata (seed, C, dataset statistics hash, library versions, sizes) and headline metrics |

`LinearTextModel.load()` calls `np.load(..., allow_pickle=False)` for both arrays, so an object
array is refused. It also checks the dtype, the shape against the feature configuration, that
all values are finite, and the format version. The `HashingVectorizer` is stateless and is
rebuilt from `meta.json`, so no fitted vocabulary has to be stored.

### 6.4 Why not a transformer encoder

Fine-tuned transformer classifiers such as DeBERTa-style prompt-injection models and Llama
Prompt Guard are the usual choice in the literature and in products [6], [7]. We chose hashed
n-grams with a linear model for this version for four reasons:

1. **Latency budget on CPU.** The detector is inline: every untrusted tool result is scanned
   before the agent sees it, and one agent step can return several results. The specification
   target is p50 < 10 ms for 2 KB of text. A linear model over sparse features meets this on
   one CPU core (section 13.4). A transformer encoder with around 100M parameters costs much
   more CPU time per 512-token window, and a 10 KB result needs several windows. We have not
   benchmarked one on our hardware; that comparison is part of the future work below.
2. **No GPU.** Mirsad is meant to be self-hosted by small organisations with Docker on ordinary
   servers. The deployment target has no accelerator.
3. **Dataset size.** The team's authored dataset holds hundreds to a few thousand labelled
   examples, with separate test batches per language. A large encoder fine-tuned on that much
   data can overfit to authoring style. With so few test examples, that overfitting would be
   hard to detect. Character n-grams generalise reasonably across Arabic morphology, spelling
   variants, dialect and Arabizi, where subword tokenisers trained mostly on MSA or English
   break words into fragments. Arabic encoders exist: AraBERT [8], ARBERT/MARBERT [9] and
   CAMeLBERT [10]. The CAMeLBERT study found that it matters how close the pre-training variety
   is to the task variety [10], which is a concern for Gulf dialect and Arabizi.
4. **Auditability and safety.** Linear weights and explicit rule spans make every score
   explainable. The spans are also exactly what `sanitize()` needs. Plain-array persistence
   (6.3) avoids shipping executable model files.

The cost is that the model has no semantic understanding. A paraphrase that shares few surface
n-grams with the training data can evade both the model and the rules (section 16).
**Future work:** fine-tune a multilingual or Arabic encoder (or distil one into a small
student) on the same splits. Export it to ONNX for CPU inference. Compare it with this baseline
on the same test batches, with the same latency measurement. Use it as a second-stage scorer
only for texts that the cheap stage scores in an uncertain band.

## 7. Ensemble and calibration

The final score combines the model score `m` and the rule score `r` with a noisy-OR:

```
raw   = 1 − (1 − m)^α · (1 − r)^β
score = calibrate(raw, pivot)    # piecewise-linear and monotone; pivot ↦ 0.5, 0 ↦ 0, 1 ↦ 1
```

A noisy-OR fits because the two sources fail independently. The rules are precise on known
phrasings and the model covers paraphrase and dialect. A confident hit from either one should
raise the score without the other having to agree. The exponents α and β and the decision point
`pivot` are tuned on the **validation split only**. The objective is maximum F1 subject to a
false positive rate of at most 5 %. Calibration then moves the tuned operating point to 0.5,
so the policy defaults keep their meaning: `flag_threshold: 0.5` is the tuned operating point
and `block_threshold: 0.8` is a stricter one. Operators can still re-threshold each tool in the
policy. The label in a `DetectionResult` uses 0.5 and 0.8, and the gateway re-labels it with
the tool's own thresholds.

## 8. Actions

### 8.1 Mapping in the gateway

| Score | Action |
|---|---|
| `< flag_threshold` | pass |
| `≥ flag_threshold` and `< block_threshold` | flag (content unchanged; audited; `label = suspicious`) |
| `≥ block_threshold` | the tool's `on_detect`: `sanitize` (default), `block` or `flag` |

A detection labelled `injection` also sets `injection_detected` on the session, which arms the
taint rule `TAINT_AFTER_INJECTION` for later high-risk calls. In `mode: monitor` the action is
computed and audited but not applied.

### 8.2 `sanitize(text, detection, mode="sanitize")`

* Each rule span is widened to the sentence or line that contains it, by at most 300
  characters on each side. Sentence ends include the Arabic question mark. Spans of structural
  rules (hidden HTML, base64 blobs, markdown-image exfiltration, chat-template tokens) already
  cover a whole element, so they are removed exactly.
* If only the model fired, its top windows are removed.
* Regions that overlap, or that are separated by a short gap (≤ 120 characters) inside one
  paragraph, are merged. Each region is replaced by
  `[⚠ Mirsad: removed suspected instruction | تمت إزالة تعليمات مشبوهة]`.
* **Fail closed:** if the detection is positive (≥ 0.5) but has no span to cut, the content is
  withheld as in block mode.

`mode="block"` returns
`[⛔ Mirsad: content withheld — suspected prompt injection (score 0.93). | مرصاد: تم حجب المحتوى — …]`
whatever the spans are. For JSON results, `sanitize_structured()` rewrites only the string
leaves that score above the threshold.

### 8.3 Spotlighting (`spotlight()`)

Spotlighting was proposed by Hines et al. [3]. It transforms untrusted text so that the model
keeps a continuous signal of where the text came from. The paper describes three variants:
*delimiting* (wrap the text in markers), *datamarking* (interleave a marker character through
the text) and *encoding* (for example base64). Mirsad implements the first two:

* `mode="delimit"` (default) wraps the content between
  `⟦MIRSAD-DATA source="…" call_id="…" boundary="<16 hex>"⟧` and
  `⟦/MIRSAD-DATA boundary="…"⟧`. A bilingual note says that the block is untrusted data
  returned by the named tool and that instructions inside it must not be followed.
* `mode="datamark"` also replaces runs of spaces and tabs inside the content with `ˆ`, the
  marker used in the paper, and extends the note.

The paper notes that plain delimiters are weak because an attacker can forge the closing
marker. Mirsad reduces this risk in two ways. The boundary is the first 16 hex digits of
SHA-256(call id, source, content), so the content cannot contain a marker that matches its own
boundary. Any `⟦`/`⟧` brackets inside the content are also replaced with ASCII brackets before
wrapping. Unlike the paper, Mirsad sits outside the agent and cannot edit its system prompt,
so the instruction travels inside the tool result. Spotlighting is therefore defence in depth.
It has been broken by adaptive search attacks [5], and how datamarking affects Arabic script
has not been studied [3].

## 9. Structured results

`scan_structured(value)` walks a JSON-like value (dicts, lists, tuples, pydantic models). It
scans every string that contains a letter, including keys, and returns the maximum score. All
leaves are featurised in one batch. Leaves shorter than 12 characters (ids, dates) skip the
model. Spans are expressed in coordinates of `json.dumps(value, ensure_ascii=False)`. The
detector builds that dump itself and keeps a per-character position map through JSON escapes.
This means the dashboard can highlight the exact characters in the stored JSON. Scanning leaves
separately also defeats payloads that are hidden with `\uXXXX` escapes in the raw JSON text.
The gateway scans the text form as well when it differs from the dump.

## 10. Arabic-specific challenges

These are the reasons for the Arabic handling above, described without examples:

* **Optional diacritics.** Tashkeel is normally omitted, so the same word appears with or
  without marks. Marks can also be inserted, stacked or repeated to break keyword matching
  while the text stays readable. Normalisation removes them, and abnormal patterns raise a
  signal.
* **Letter variants and look-alikes.** Hamza carriers, alef forms, alef maqsura vs ya, and ta
  marbuta vs ha are used interchangeably in informal writing. Persian and Urdu letters render
  almost identically to Arabic ones. Arabic-Indic and Persian digits are both common. All of
  these are folded.
* **Rich morphology.** Conjunctions, prepositions, the article and pronoun suffixes attach to
  the word, so one orthographic word can carry a whole phrase. Rule macros allow optional
  clitics, and the model's character n-grams match on stems without a morphological analyser.
* **Dialects.** Gulf, Egyptian and Levantine dialects use different vocabulary, negation and
  imperative forms from MSA. Work on multilingual and Arabizi jailbreaks shows that safety
  behaviour learned mostly from English data transfers poorly to lower-resource languages and
  to Arabic written in transliteration or Arabizi [11], [12]. The rule base has
  separate Gulf-dialect patterns. The dataset schema records `variety` so that recall can be
  reported per variety.
* **Arabizi.** Latin letters with digits for Arabic sounds have no standard spelling. Language
  identification recognises Arabizi, a dedicated rule file covers frequent forms, and character
  n-grams tolerate spelling variation. Recall on Arabizi is expected to be lower and must be
  reported separately.
* **Code-switching.** Arabic and English are mixed inside one sentence, often with the Arabic
  article attached to English words. Rules from both languages run on every text, `mixed` is a
  first-class label, and a separate test split measures it.
* **Bidirectional text.** Mixing right-to-left and left-to-right text legitimately uses direction
  marks. Override and isolate controls, however, can make the order a human sees differ from
  the logical order the model reads. Controls are removed and signalled; routine marks are
  removed silently.

## 11. Dataset

### 11.1 Record schema

One JSON object per line (`data/detector/raw/<batch>.jsonl`):

| Field | Type / values | Notes |
|---|---|---|
| `id` | string, unique across all files | e.g. `ar-ben-0042` |
| `text` | string, 1–50,000 characters | the content as it would appear in a tool result |
| `label` | `1` / `0` | 1 = prompt injection (see 11.2), 0 = benign |
| `lang` | `en` / `ar` / `mixed` | decides the test split |
| `variety` | `en` / `msa` / `gulf` / `egyptian` / `levantine` / `arabizi` / `mixed` | |
| `carrier` | `email` / `web` / `document` / `crm_note` / `chat` / `tool_output` / `review` / `ticket` / `code_comment` / `plain` | |
| `attack_type` | `none` / `goal_hijack` / `data_exfiltration` / `tool_misuse` / `role_impersonation` / `context_ignoring` / `obfuscated` / `payload_splitting` / `social_engineering` / `markdown_exfil` / `system_prompt_leak` | `none` for benign records |
| `difficulty` | `easy` / `medium` / `hard` | |
| `source` | string | authoring batch or upstream dataset; filled automatically if empty |
| `notes` | string | free text |

Invalid lines are reported with file and line number and then skipped. Invalid means not JSON,
a missing or unknown enum value, a non-binary label, blank text or a duplicate id. Soft
inconsistencies are counted in `stats.json` and the record is kept. These are a benign record
with an attack type, a positive record without one, a language/variety mismatch, and unknown
fields.

### 11.2 Labelling guideline (summary)

* **1:** the text contains an instruction aimed at an AI agent or model. The instruction tries
  to change the agent's behaviour or to trigger actions that the agent's user did not request.
* **0:** everything else. This explicitly includes **hard negatives**:
  * ordinary imperatives addressed to people, such as customer requests and internal how-tos;
  * articles that *describe* attacks;
  * examples clearly framed as quotations;
  * text that mentions AI assistants without instructing them.

Hard negatives should make up a large share of the benign data. They are what keeps the false
positive rate honest.

### 11.3 Building the splits (`python -m mirsad.detector.build_dataset`)

1. Load and validate `raw/*.jsonl` (authored batches) and `external/*.jsonl` (public datasets,
   each with a licence note).
2. **Deduplicate** by the SHA-256 of the *normalised* text. Copies that differ only in case,
   invisible characters, diacritics and so on count as the same text. When a text also appears
   in a test batch, the **test copy wins**. A text that is labelled both 0 and 1 is dropped
   everywhere and listed.
3. **Group split by batch.** A file whose name starts with `test-` is a held-out batch. Its
   records go to `test_en`, `test_ar` or `test_mixed` according to `lang`. External test
   batches go to `test_ext_<name>`. All other batches are pooled and split 85/15 into `train`
   and `val`, stratified by (label, language), with a fixed seed. Test batches never reach
   training, even partly.
4. **Augment `train` only.** Augmented records are marked `source: aug/…` and get an id suffix
   `~aug-…`. Three kinds are produced:
   * positives embedded at the start, middle or end of benign carriers, using a carrier in the
     same language when one exists;
   * benign-benign concatenations, so that text length cannot become a shortcut;
   * obfuscation variants for half the positives and 10 % of the negatives: zero-width
     characters, homoglyphs, tashkeel, spacing noise and Arabic elongation. Obfuscating
     negatives too stops obfuscation from becoming a label shortcut.
5. **Leakage check.** No test text hash and no test id (before the `~` suffix) may appear in
   train or val. Augmented variants that collide with a test text are removed. The result is
   recorded in `stats.json`.
6. Write `splits/{train,val,test_en,test_ar,test_mixed,test_ext_*}.jsonl` and `splits/stats.json`.
   `stats.json` holds inputs, invalid lines, warnings, duplicates, batch→split assignment,
   augmentation counts, leakage check and per-split distributions.

### 11.4 How the team supplies training data

1. Write batches as `data/detector/raw/<batch>.jsonl` following 11.1. Use one author and one
   topic per batch where possible, for example `ar-gulf-email-02.jsonl`.
2. Write **held-out test batches** as `raw/test-<name>.jsonl`. Test batches should be written by
   a different team member, or at a different time, from the training batches, and never by
   paraphrasing training items. The group split prevents verbatim leakage only, not leakage of
   style.
3. Cover every language and variety, every carrier and every attack type in both splits, with
   benign hard negatives in each. Aim for at least 150 records per test language so that the F1
   confidence interval is useful.
4. Put public datasets under `data/detector/external/` together with their licence and
   provenance, and document them in `data/detector/DATASHEET.md`. That file is owned by the
   data authors and does not exist yet.
5. Run `python -m mirsad.detector.build_dataset --data data/detector` and read the summary: it
   prints invalid lines, duplicates, label conflicts and the leakage check.

## 12. Training and evaluation

### 12.1 Procedure (`python -m mirsad.detector.train`)

1. Fit the logistic regression on `train` for each C in the grid (default 0.5, 2, 8). Keep the
   C with the best validation PR-AUC, where validation texts are scored with sliding windows as
   in production.
2. On `val` only, choose α and β from {0.5, 0.75, 1, 1.5, 2}² and the ensemble pivot by
   maximum F1 subject to FPR ≤ 5 %. The model-only and rules-only operating points are chosen
   the same way, for the ablation. Test splits are never used for any choice; a unit test
   checks that changing the test splits changes neither the weights nor any threshold.
3. Evaluate every split under three systems: ensemble, model only and rules only. Results are
   broken down by language, variety, carrier, difficulty and attack type. The script also
   produces a threshold sweep, scan latency for 0.5, 2 and 10 KB texts, and figures.

### 12.2 Metric definitions

With TP, FP, TN, FN counted at the threshold (positive = score ≥ threshold):

| Metric | Definition |
|---|---|
| Precision | TP / (TP + FP) |
| Recall (TPR) | TP / (TP + FN) |
| F1 | 2 · P · R / (P + R) |
| FPR | FP / (FP + TN): share of benign texts flagged. This is the over-defence cost [13]. |
| FNR | FN / (FN + TP) |
| Accuracy | (TP + TN) / n |
| ROC-AUC | area under TPR vs FPR over all thresholds; threshold-free ranking quality |
| PR-AUC | average precision; more informative than ROC-AUC under class imbalance |
| Confusion matrix | `[[TN, FP], [FN, TP]]` |
| Recall by attack type | share of positives of each `attack_type` scored ≥ threshold |
| Latency p50 / p95 | median and 95th-percentile wall time of `scan()` per text size, single thread, after warm-up |

The AUCs are reported as `null` for a split that contains only one class. Unless stated
otherwise, all numbers are at the calibrated flag threshold 0.5. `ensemble_at_block_threshold`
gives the same metrics at 0.8, and `rules_only_fallback` gives what rules-only mode does in
production at 0.5.

### 12.3 Outputs

* `src/mirsad/detector/model/{coef.npy, intercept.npy, meta.json}`.
* `reports/detector_metrics.json`: configuration, selection details (C search, top ensemble
  candidates), per-split metrics for the three systems, breakdowns, threshold sweep, latency,
  and target checks (`f1_test_en_ge_0.85`, `f1_test_ar_ge_0.85`, `p50_2kb_lt_10ms`).
* `reports/figures/`: `confusion_matrices.png`, `roc_curves.png`, `pr_curves.png`,
  `threshold_sweep.png`, `per_language_f1.png`, `ablation_f1.png`.

### 12.4 Retraining and shipping a model

```bash
python -m mirsad.detector.build_dataset --data data/detector
python -m mirsad.detector.train --data data/detector --out src/mirsad/detector/model --reports reports
# equivalently: mirsad detector train --data data/detector --build
```

On a laptop CPU, training on a few hundred records takes about 2 s. Datasets of a few thousand
records should still finish well within a minute. After retraining:

1. Read `reports/detector_metrics.json`, especially the test splits and the per-variety
   breakdown.
2. Run `pytest tests/detector` and the gateway and bench tests.
3. Commit the three model files together with the metrics report.

The running gateway loads the model at start-up. Restart it to pick up a new model.
`detector.version` changes with every new set of weights.

## 13. Results

> **TO BE FILLED after the shipped model is trained on the team's dataset.**
> Fill these tables from `reports/detector_metrics.json` produced by the final training run.
> Do not use numbers from the synthetic pipeline check described below.

### 13.1 Held-out test performance (ensemble, threshold 0.5)

| Split | n | Precision | Recall | F1 | FPR | ROC-AUC | F1 rules only | F1 model only |
|---|---|---|---|---|---|---|---|---|
| val | | | | | | | | |
| test_en | | | | | | | | |
| test_ar | | | | | | | | |
| test_mixed | | | | | | | | |
| test_ext_… | | | | | | | | |

Targets: F1 ≥ 0.85 on `test_en` and `test_ar`. FPR ≤ 5 % at the flag threshold.

### 13.2 Breakdown by variety and attack type

*(to be filled: recall per `variety`, including Gulf and Arabizi, and per `attack_type`; FPR on
hard negatives)*

### 13.3 Figures

*(to be embedded: confusion matrices, ROC and PR curves, threshold sweep, per-language F1,
ablation)*

### 13.4 Latency

Preliminary measurements, taken before the final training. Latency depends on the feature
dimension and the text, not on the values of the weights, so these numbers carry over to the
final model. They were measured on 2026-10-11 on an Apple M5 laptop with Python 3.12, one
thread, 200 repetitions after warm-up, on benign text from `data/detector/raw/`. The ensemble
used a full-size model (2^20 + 2^18 features) from the synthetic pipeline check.

| Text size | Rules only p50 / p95 (ms) | Ensemble p50 / p95 (ms) |
|---|---|---|
| 0.5 KB | 0.45 / 0.58 | 1.08 / 1.29 |
| 2 KB | 1.87 / 2.03 | 3.40 / 3.70 |
| 10 KB | 11.74 / 11.98 | 18.44 / 21.02 |

The 2 KB target (p50 < 10 ms) is met with margin. Re-measure these on the deployment hardware
and on the final model.

### 13.5 Pre-training observations

* **Rules-only false positives on the current benign batches** (2026-10-11, threshold 0.5):
  `ar-ben` flags 6 of 100 records (6.0 %) and `en-ben` flags 3 of 260 (1.2 %), 9 of 360 pooled
  (2.5 %). The Arabic batch is above the 5 % FPR target for the rules-only fallback. The
  records and rules involved are:
  * `ar-ben-0019` and `ar-ben-0052`: `ar.ctx.ignore_instructions` and `ar.ctx.ignore_previous`
  * `ar-ben-0061` and `ar-ben-0097`: `ar.addr.vocative`
  * `ar-ben-0063`: `ar.act.without_confirmation`
  * `ar-ben-0094`: `ar.secret.without_user_knowing`
  * `en-ben-0057`: `en.leak.mention` and `struct.role.json_role`
  * `en-ben-0063`: `en.ctx.ignore_everything`
  * `en-ben-0107`: `en.exfil.send_secrets` and `en.act.disable_security`

  These records should go to the rule authors for error analysis. The ensemble should reduce
  these false positives because its operating point is tuned for FPR ≤ 5 %; check this after
  training.
* **Pipeline check.** `build_dataset` and `train` were run end to end on neutral synthetic
  placeholder records, where the positive class is just the presence of a placeholder token.
  The purpose was to prove the pipeline only; the resulting scores mean nothing about
  injection detection. The shipped `model/` directory was not created, so the packaged
  detector currently runs in rules-only mode.

## 14. Public API

```python
from mirsad.detector import (InjectionDetector, normalize, detect_language, RuleSet, sanitize, spotlight,
                             sanitize_structured, block_notice, load_model)

det = InjectionDetector.default()            # packaged model, or rules-only fallback
det = InjectionDetector(model_dir, window_chars=600, stride_chars=300, rules=None, model=None)
det.scan(text) -> DetectionResult            # score, label, language, spans, signals, model_score, rule_score
det.scan_many(texts) -> list[DetectionResult]
det.scan_structured(value) -> DetectionResult   # spans in json.dumps(value, ensure_ascii=False) coordinates
det.mode -> "ensemble" | "rules_only";  det.version -> str;  det.info() -> dict

normalize(text) -> NormalizedText(text, signals, offsets, original)   # .to_original(), .from_original()
detect_language(text) -> "en" | "ar" | "mixed" | "other"
sanitize(text, detection, *, mode="sanitize" | "block") -> str
spotlight(text, *, source, call_id, mode="delimit" | "datamark") -> str
```

The package's `__init__` re-exports the functions `normalize` and `sanitize`, and these
shadow the submodules of the same names. To reach module-level constants, import them by name,
e.g. `from mirsad.detector.normalize import SIG_BIDI`, or use `importlib.import_module`.

## 15. Testing

`pytest tests/detector` runs 227 tests in about 7 s. The suite contains **no adversarial text**.
Positive detections come from a stub rule that matches the neutral placeholder token
`SAMPLE-FLAGGED-TEXT`, or from hand-built `DetectionResult`s. Every dataset and model is built in
a temporary directory from neutral synthetic records (`tests/detector/neutral_data.py`), where
the positive class is the presence of the token `AAA`. Covered:

* normalisation of every character class, with offset-map round trips;
* language identification (EN, AR including Gulf, mixed, Arabizi, other);
* benign EN, AR and mixed business texts staying below the flag threshold, with and without a
  model;
* rules-only fallback for missing and corrupt model files;
* label thresholds, span mapping through invisible characters, and structured scanning through
  JSON escapes and non-string keys;
* `sanitize`, block and `spotlight` output structure;
* pickle-free save and load, including a spy on `np.load(allow_pickle=False)` and refusal of
  object arrays;
* windowed scoring and the ensemble arithmetic;
* dataset validation, dedup, group split, test isolation and augmentation marking;
* training artefacts, metrics, figures, and independence of the tuning from the test splits;
* both `python -m` entry points (marked `slow`), and p50 latency below a generous 50 ms bound.

Whether the packaged rules catch real attack phrasings is outside this suite. The YAML
`examples` and `negatives` are reviewed and tested by the rule authors.

## 16. Limitations

* **Surface-level model.** Paraphrases, translations into an unseen variety, and instructions
  that are split across fields or across several tool results can evade both rules and model.
  Adaptive attackers who can query the detector will find such inputs [4], [5]. The taint and
  policy layers exist for this reason.
* **Data-bound quality.** The model can only be as good as the authored dataset. The model is
  not yet trained (section 13). Dialect and Arabizi coverage depends on how many records the
  team writes for them.
* **Rules-only fallback.** Without a model, recall depends on the rule base alone. On the
  current Arabic benign batch its false positive rate is above target (13.5).
* **Normalisation trade-offs.** Folding look-alikes and joining letter-spaced words can, rarely,
  change benign text. Homoglyph folding is limited to Latin contexts, so attacks written
  entirely in Cyrillic or Greek look-alikes inside non-Latin text are not folded. Encodings
  other than base64 (hex, ROT13, URL encoding) are not decoded.
* **Long inputs.** Latency grows linearly with size, about 18 ms p50 for 10 KB with the model.
  The gateway truncates very large results (`max_result_chars`).
* **Sanitisation is heuristic.** Widening to sentences can remove benign text next to an
  injection, and it can leave parts of a multi-sentence instruction behind. Spans in a
  structured result are cleaned per leaf; if that is not possible, the gateway blocks.
* **Spotlighting is advisory.** It depends on the downstream model honouring the markers. Its
  effect on Arabic text is unstudied [3], [5].
* **Calibration is per dataset.** The 0.5 and 0.8 thresholds mean "tuned operating point" and
  "stricter point" for the validation data the model was trained with, not probabilities.
  Content distributions in deployment may differ, so the monitor mode should be used to tune
  thresholds per tool.

## References

[1] K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," in *Proc. 16th ACM Workshop Artif. Intell. Secur. (AISec '23)*, Copenhagen, Denmark, 2023, pp. 79–90, doi: 10.1145/3605764.3623985.

[2] Y. Liu, Y. Jia, R. Geng, J. Jia, and N. Z. Gong, "Formalizing and benchmarking prompt injection attacks and defenses," in *Proc. 33rd USENIX Secur. Symp. (USENIX Security 24)*, Philadelphia, PA, USA, Aug. 2024, pp. 1831–1847.

[3] K. Hines, G. Lopez, M. Hall, F. Zarfati, Y. Zunger, and E. Kıcıman, "Defending against indirect prompt injection attacks with spotlighting," in *Proc. Conf. Applied Machine Learning in Information Security (CAMLIS 2024)*, CEUR Workshop Proceedings, vol. 3920, Arlington, VA, USA, Oct. 2024, pp. 48–62. Preprint: arXiv:2403.14720.

[4] W. Hackett, L. Birch, S. Trawicki, N. Suri, and P. Garraghan, "Bypassing LLM guardrails: An empirical analysis of evasion attacks against prompt injection and jailbreak detection systems," in *Proc. 1st Workshop on LLM Security (LLMSEC)*, Vienna, Austria, Aug. 2025, pp. 101–114.

[5] M. Nasr et al., "The attacker moves second: Stronger adaptive attacks bypass defenses against LLM jailbreaks and prompt injections," in *Proc. 35th USENIX Security Symp. (USENIX Security 26)*, Baltimore, MD, USA, Aug. 2026, pp. 1467–1486. Preprint: arXiv:2510.09023.

[6] Protect AI, "deberta-v3-base-prompt-injection-v2," model card, Hugging Face. [Online]. Available: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2 (accessed Oct. 11, 2026).

[7] Meta, "Llama Prompt Guard 2 86M," model card, Hugging Face. [Online]. Available: https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M (accessed Oct. 11, 2026).

[8] W. Antoun, F. Baly, and H. Hajj, "AraBERT: Transformer-based model for Arabic language understanding," in *Proc. 4th Workshop Open-Source Arabic Corpora Process. Tools (OSACT4)*, Marseille, France, May 2020, pp. 9–15.

[9] M. Abdul-Mageed, A. Elmadany, and E. M. B. Nagoudi, "ARBERT & MARBERT: Deep bidirectional transformers for Arabic," in *Proc. 59th Annu. Meeting Assoc. Comput. Linguistics and 11th Int. Joint Conf. Natural Lang. Process. (ACL-IJCNLP)*, Aug. 2021, pp. 7088–7105, doi: 10.18653/v1/2021.acl-long.551.

[10] G. Inoue, B. Alhafni, N. Baimukan, H. Bouamor, and N. Habash, "The interplay of variant, size, and task type in Arabic pre-trained language models," in *Proc. 6th Arabic Natural Lang. Process. Workshop (WANLP)*, Kyiv, Ukraine (Virtual), Apr. 2021, pp. 92–104.

[11] Y. Deng, W. Zhang, S. J. Pan, and L. Bing, "Multilingual jailbreak challenges in large language models," in *Proc. 12th Int. Conf. Learn. Represent. (ICLR)*, 2024. [Online]. Available: https://arxiv.org/abs/2310.06474

[12] M. Al Ghanim, S. Almohaimeed, M. Zheng, Y. Solihin, and Q. Lou, "Jailbreaking LLMs with Arabic transliteration and Arabizi," in *Proc. 2024 Conf. Empirical Methods Natural Lang. Process. (EMNLP)*, Miami, FL, USA, Nov. 2024, pp. 18584–18600, doi: 10.18653/v1/2024.emnlp-main.1034.

[13] H. Li, X. Liu, N. Zhang, and C. Xiao, "PIGuard: Prompt injection guardrail via mitigating overdefense for free," in *Proc. 63rd Annu. Meeting Assoc. Comput. Linguistics (Vol. 1: Long Papers)*, Vienna, Austria, Jul. 2025, pp. 30420–30437, doi: 10.18653/v1/2025.acl-long.1468.
