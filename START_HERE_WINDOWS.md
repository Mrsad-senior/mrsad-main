# Mirsad — consolidated source update (2026-10-29)

This is **the complete project source**, not a partial patch. It consolidates the
Dynamic Finance/Healthcare sectors, original-task and behavioral checks,
LLM Judge revisions, custom unseen-attack sandbox, and Arabic response behavior.
It also carries the 20-example multilingual semantic reference library and the
English-only LLM Judge reporting instruction tested during development.

## Windows — install and run

**Important:** Keep your existing folder as a backup. This archive does **not**
contain your old `.mirsad/` database, passwords, `.venv/`, or local Ollama models.
Do not paste passwords into chat or upload `.mirsad/` to GitHub.

1. Extract the entire archive to a **new** folder. In VS Code, open its
   `mrsad-main-main` directory (the one containing `pyproject.toml`).
2. Open PowerShell terminal in that folder:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -e ".[semantic]"
   .\.venv\Scripts\python.exe -m pip install pytest pytest-asyncio
   .\.venv\Scripts\python.exe -m pytest tests/upgrade tests/demo -q
   ```

   The optional embedding model downloads when semantic detection is first
   enabled; it is NOT embedded in the ZIP.

3. Build the updated dashboard (**required in this archive**):

   ```powershell
   cd web
   npm ci
   npm run build:gateway
   cd ..
   ```

   The Python source contains the latest web UI, but the prebuilt static files
   bundled with this ZIP are an earlier build. These three commands produce
   the correct dashboard. Vite is pinned to the patched **7.3.7** release.

4. In a separate terminal, launch your installed Ollama server (`ollama serve`,
   only if not already running). Ensure `ollama list` includes `qwen2.5:7b`.
5. Initialize a **new demo** if the new folder has no `.mirsad` directory:

   ```powershell
   .\.venv\Scripts\mirsad.exe init --demo
   ```

   Store credentials privately. Never run init again merely to restart.
6. Launch Mirsad **in the same PowerShell session as these variables**:

   ```powershell
   $env:MIRSAD_JUDGE_ENABLED="1"
   $env:MIRSAD_JUDGE_MODEL="qwen2.5:7b"
   $env:MIRSAD_SEMANTIC_ENABLED="1"
   .\.venv\Scripts\mirsad.exe serve --demo
   ```

   Open http://127.0.0.1:8700 and use the Demo Console. If you have slower
   hardware, semantic startup may be slower due to local model loading.

## What is done; what is not proven

- **Implemented:** Finance/Healthcare mock tools and scenarios, policy packs,
  English/Arabic agent responses, forged-authority LLM Judge prompts,
  internal English explanations, and custom unseen-attack sandbox.
- **Implemented but heuristic:** intent checking, multi-call behavior rules,
  and multilingual embedding-similarity matching. These can produce false
  positives and false negatives. The semantic score is **evidence**, not
  a calibrated attack probability; the reference corpus is just 20 examples.
- **Tested previously on user's machine:** local Qwen judged selected Arabic and
  English attacks, blocked poisoned invoices and doctored notes, and permitted
  one human-approved *synthetic* Healthcare send. These observations do not
  establish accuracy on genuinely independent held-out attacks.
- **Not validated in this build environment:** fresh JavaScript compilation,
  real local Ollama model inference, or full API integration. Verify locally
  after installation. Backend test subset results are in `TEST_REPORT.txt`.
- **Security model:** Never put real financial, customer, or patient data in
  this demo. Deny rules and human approval are necessary even when model-based
  inspection misses a prompt injection.

## Smoke tests

```powershell
.\.venv\Scripts\python.exe scripts/semantic_language_test.py
.\.venv\Scripts\python.exe -m pytest tests/upgrade -q
```

`scripts/semantic_language_test.py` contains the eight examples used during
manual development; **do not** treat them as an independent test set. Collect
new hold-out malicious and benign examples and calibrate score thresholds
before reporting precision, recall, F1, or claiming production readiness.

## Integration notes

- This is not a Git clone and contains no `.git` history; review and merge
  into your shared team repository instead of blindly replacing teammates' work.
- Only the frontend lockfile and Vite package pin were updated; your local
  npm dependency installation may need `npm ci` before `npm run build`.
- All demonstrations involve fake accounts and patients only.
