# Mirsad: Dynamic detection and sector-pack upgrade

Status: **implementation prototype**. This is a source-code handoff, not a production certification.

## Architectural summary

The existing gateway's allow/deny policy, taint tracking, injection rules, audit log, and approvals remain intact. Additional layers are:

1. **Keyword/rule detector (existing):** fast scan of each tool result.
2. **Multilingual semantic detection (optional):** local SentenceTransformer similarity against synthetic Arabic/English attack examples; injected embedding callables make tests deterministic.
3. **Second-model content judge (optional):** a local Ollama-compatible classifier returning a score and a short reason. Text is wrapped as untrusted JSON, with a classifier-only system instruction.
4. **Original-task alignment:** each protected demo run binds an authenticated user task before the LLM invokes any tool. A conservative operation-class check rejects unrequested sensitive operations. An optional *separate* local LLM intent judge assesses whether a side effect serves the original task.
5. **Behavior patterns:** repeated exports, high read volume followed by external sends, and transitions absent from an explicitly reviewed benign sequence baseline (only when configured).
6. **Business rules:** Finance and Healthcare policy rules operate independently of content and intent classifier confidence.

`DetectionResult.score` is the max of available content-layer scores and includes `layer_scores` and `layer_reasons`. Gateway tool-call `Decision.risk_score` also reflects policy, taint and intent/behavior evidence. **These are two decision points**, not a statistically calibrated end-to-end attack probability. The dashboard displays both. Because semantic and judge scores do not identify safe span boundaries, high-confidence detections cause the **entire untrusted result to be withheld** rather than partially sanitized.

### Configuration

The optional local inference capabilities are disabled by default to preserve the existing fast demo and tests. **With those flags off, text classification still lacks the proposed semantic generalization.** This is an explicit limitation, not a claim of zero-keyword detection.

```bash
python -m pip install -e '.[semantic]'
ollama pull qwen2.5:3b
# Optional: multilingual embedding model downloads on initial use;
# cache weights before offline demonstrations.
export MIRSAD_SEMANTIC_ENABLED=1
export MIRSAD_JUDGE_ENABLED=1
export MIRSAD_INTENT_JUDGE_ENABLED=1
export MIRSAD_JUDGE_MODEL=qwen2.5:3b
```

On Windows PowerShell replace `export VAR=value` with `$env:VAR="value"`. The default demo agent still needs its configured Ollama LLM (usually `qwen2.5:7b`). `MIRSAD_SEMANTIC_ENABLED=1` requires the optional package and model weights; enabled but unavailable detectors **fail closed**, not silently downgraded. All model calls are local by default. Mock providers in tests require no API keys and must not be portrayed as genuine model performance.

**Important:** A small local model might not reliably return structured JSON. A malformed or timed-out required judge leads to denial of affected untrusted tool results or sensitive actions. Verify latency and error handling with the chosen model before a live demonstration.

### Finance and Healthcare demo

On the dashboard's Demo Console, use the **Sector / القطاع** dropdown to select General, Finance, or Healthcare. This uses the new `/api/demo/*?sector=finance|healthcare` routes (chat accepts `sector` in JSON), isolates each fake world, loads a matching set of attack scenarios, and chooses the correct agent ID and policy from `configs/policies/sectors.yaml`.

The Finance fake world supports `get_account_balance`, `get_customer_profile`, `read_invoice`, `transfer_funds`, and `approve_payment`. The Healthcare fake world supports `get_patient_record`, `update_prescription`, `book_appointment`, and `send_lab_results`. Everything is synthetic and stored only in memory. The standard General world is unchanged. The sector packs currently run through the **Demo Console agent backends**; adding them to the standalone MCP workspace server would require additional adapters.

**Finance enforcement:** amounts over SAR 10,000 request approval; unknown mock beneficiary IBANs request approval; `approve_payment` always requests approval; a transfer unrelated to the original trusted task is denied. The allowed beneficiary is a synthetic, code-defined demo registry, not a bank verification service.

**Healthcare enforcement:** `update_prescription` always requests approval; `send_lab_results` to domains other than `najd-health.example` is denied; the security monitor independently denies external patient disclosure; sensitive categories in outbound arguments raise review requirements. For a real healthcare implementation, an authorization policy must consider legal basis, consent, user role, and purpose limitation; this prototype does not.

### Attack examples

- `finance-invoice-en` and `finance-invoice-ar`: external invoice tries to instruct the AI to transfer funds to an untrusted IBAN during a summarize-only task.
- `health-note-en` and `health-note-ar`: forged doctor note tries to send patient data to an external address during a summarize-only task.

The rule-only baseline may miss these variants. The agent's actual behavior remains model-dependent, and a protected run may stop before the malicious tool call. **Do not claim actual attack-success reduction from these mock scenarios** without a repeatable benchmark.

### Testing

```bash
python -m pytest --override-ini addopts='' -q tests/upgrade tests/demo/test_agent.py tests/demo/test_world.py tests/detector tests/policy tests/taint
```

Local validation (2026-10-29): **668 passed**. Tests include fake semantic/judge providers, malicious Arabic/English variants, intent and behavior rules, policy parameters, fake tool schemas, and scenario planting. These are unit and component tests; they do **not** validate a live Ollama model's reliability, a deployed FastAPI server, or the React dashboard build.

The web build could not be performed in this environment because dependencies were unavailable through the npm cache and installation failed. **The updated dashboard is in `web/src/`, but `src/mirsad/static/` is the older build.** Run the documented project build command in an environment with npm access:

```bash
cd web
npm ci
npm run build
```

That should run TypeScript checks and emit the updated assets into `src/mirsad/static/`. Only then use the served dashboard to validate the sector selector.

### Unfinished validation and limitations

- Real semantic detection and local judge require installed models and **calibration on held-out Arabic/English attacks and benign samples**, especially to estimate false positives and F1.
- The score is a conservative heuristic, not a probability. With only keyword rules enabled, new semantic threats may be missed; independent policy/intent checks mitigate impact.
- The heuristic intent pre-check uses operation/task terms; for stronger generalization enable `MIRSAD_INTENT_JUDGE_ENABLED=1`. Local LLM judges can also be fooled; keep hard rules.
- The sequence anomaly check uses reviewed benign traces only if `fit_benign_traces` is called. No production baseline exists yet. Excessive legitimate reads may produce false positives.
- Current runtime task-state evidence is saved as security decision reasons in the audit trail. Policy-only audit replay does not reconstruct historical trusted task/sequence state, and will explicitly note the limitation.
- The 200 ms gateway-latency objective is not validated with new optional model calls and will likely be exceeded by synchronous local LLM inference.
- The `configs/policies/sectors.yaml` file must be present relative to the source repository when running the sector demo. Packaging via wheel/Docker needs a resource-location review.
- Role-based clinical permissions, transaction authorization, production patient consent, authentication and operational controls are outside this mock implementation. Do not connect real financial or patient data.

## Saudi regulatory relevance (illustrative, not a compliance certification)

| Mock control | General regulatory theme | Reference |
|---|---|---|
| Deny unauthorized payments, require review of risky transactions, maintain audit logs | Cybersecurity risk management; identity/access restriction; protection of information assets, integrity, and transaction security | [SAMA Cyber Security Framework](https://rulebook.sama.gov.sa/en/cyber-security-framework-2) |
| Limit financial identifiers and personal customer information sent outward | Confidentiality, access limitation, and protection against unauthorized personal-data disclosure | [Saudi Personal Data Protection Law — SDAIA guidance](https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter/details/PDPLCP) |
| Restrict patient-record disclosure and require additional controls for sensitive data | Health data is sensitive personal data, requiring additional safeguards and lawful processing | [SDAIA PDPL guidance](https://dgp.sdaia.gov.sa/wps/portal/pdp/knowledgecenter/details/PDPLCP) |

These are *design alignments*, not claims that a specific Mirsad feature satisfies a specific mandatory clause or that the software complies with SAMA or PDPL.

## Agent Lead ownership / integration checklist

- Own `demo/agent.py`, `demo/sectors.py`, and the sector demos exposed through the backend and dashboard.
- Agree with the gateway team on trusted session task-binding and enforcement semantics before merging.
- Agree with the detector team on provider install/config and safe failure paths.
- Have the dashboard team rebuild the web assets and verify approval UI with mocked financial/health data.
- Create an independently reviewed pull request. The supplied ZIP has no `.git` history and contains no live GitHub changes.
