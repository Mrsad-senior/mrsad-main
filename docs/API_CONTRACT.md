# Mirsad gateway API: what the mobile app uses

The gateway API is documented in **[docs/api.md](api.md)**, with
[audit-and-approvals.md](audit-and-approvals.md), [detector.md](detector.md) and
[web-ui.md](web-ui.md). That is the source of truth. This page only lists which
endpoints the reviewer app calls, how it reads the gateway's values, and what it
still needs (marked **proposed**). The app's adapters live in
`mobile/lib/features/*/data/`.

An earlier version of this page was a planned contract, written before the
gateway code was in the repository. It was replaced on 2026-11-02.

## Endpoints the app calls

All requests send `Authorization: Bearer <token>`, where the token is the
gateway's own JWT from `POST /api/auth/login`. The gateway does not accept
Supabase tokens.

| Screen | Endpoint | Roles allowed | Notes |
|---|---|---|---|
| Sign in | `POST /api/auth/login` `{username, password}` | any account | The form asks for an email, so reviewers need email-style usernames (allowed by the gateway). Session kept in memory only. |
| Pending approvals | `GET /api/approvals?status=pending&limit=100` | approver, admin | Polled every 15 s. |
| Approval details | `GET /api/approvals/{id}` | approver, admin | |
| Approve / reject | `POST /api/approvals/{id}/decision` `{approve, note?}` | approver, admin | `409` if already decided or expired. |
| Activity | `GET /api/audit/events?event_type=tool_call.decision&limit=100` | admin, auditor | **Approvers get `403`**; see proposal 3. |
| Audit status | `GET /api/stats/overview?hours=1` (`audit_ok`) | any account | `POST /api/audit/verify` is admin/auditor only and writes an audit event on each call. |

Dev base URL: `http://10.0.2.2:8700`, which the Android emulator maps to the
host's `127.0.0.1:8700` (the gateway's default). A physical phone needs
`mirsad serve --host 0.0.0.0` and the machine's LAN address.

## How the app reads the gateway's values

| App field | Gateway source |
|---|---|
| timestamps | epoch seconds (float), e.g. `created_at`, `expires_at`, `ts` |
| approval status | `pending` → held, `approved`, `denied` → rejected, `expired`; `cancelled` is shown as expired |
| risk score | `decision.risk_score` |
| reasons | `decision.reasons` whose `action` is not `allow` |
| reason layer | `policy`, `ratelimit`, `approval` → policy; `taint` → taint; `detector` → keywords; `system` by code: `TASK_INTENT_MISMATCH`, `UNBOUND_TASK` → intent, `SEMANTIC_TASK_MISMATCH` → LLM judge, `NEW_BENEFICIARY`, `HEALTH_DATA_EXTERNAL`, `SENSITIVE_OUTBOUND` → policy; anything else → "other check" |
| "untrusted input" badge | an objecting `TAINT_UNTRUSTED_DESTINATION`, `TAINT_UNTRUSTED_TO_EXTERNAL` or `TAINT_AFTER_INJECTION` reason |
| sector | from `agent_id`, as the gateway does: `finance-assistant` → finance, `healthcare-assistant` → healthcare, otherwise general |
| user's task | not sent by the gateway; see proposal 1 |
| arguments | shown as stored. The gateway redacts them, e.g. an IBAN becomes `SA******************1234` |
| activity decision | event `action`: `allow` → allowed, `require_approval` → held, `deny` → denied |
| activity summary | `message` of the first of the most severe reasons in `payload.reasons` |
| activity risk | `payload.risk_score`; if a trimmed payload lacks it, the low end of the `risk` band |

Held actions expire after `MIRSAD_APPROVAL_TIMEOUT_S` (120 s by default), not 5
minutes. The gateway expires them; the app only counts down to `expires_at`.

The app shows English text only for now. The gateway also sends `message_ar`
on reasons and `summary_en` / `summary_ar` on approvals.

## In the gateway, not used by the app yet

- `GET /api/stream`: Server-Sent Events for new and decided approvals. It could
  replace polling.
- `POST /api/detector/scan` `{text}` → `DetectionResult` (any account): the
  detector playground.
- `POST /api/demo/chat`, demo mode only (any account). The code also takes
  `sector` (`general`, `finance`, `healthcare`) and has
  `POST /api/demo/custom-content`; docs/api.md does not list either yet.
- `GET /api/auth/me`.

## Proposed (not in the gateway yet)

1. **`original_task` on approval records.** Guard and invoke calls already send
   `original_task`, but the record does not keep it, so the reviewer cannot see
   what the user asked. The app already reads this field when it is present.
2. **`audit_first_bad_seq` in `GET /api/stats/overview`.** This lets approvers
   see which entry broke the chain. The app already reads it when present.
3. **An activity feed approvers can read**, e.g. `GET /api/activity?limit=100`
   (approver, admin, auditor) → `{items, total}`. Items would have the
   `/api/audit/events` shape, restricted to `tool_call.decision`, with `payload`
   trimmed to `{risk_score, reasons: [{layer, code, action, message,
   message_ar}]}`. The app's model would parse it unchanged.
4. **Supabase, only if the app's `READ_SOURCE=supabase` mode is kept.** The
   gateway would accept Supabase access tokens (mapped to a role) and mirror
   `approvals` (record fields as columns, `arguments` and `decision` as jsonb,
   timestamps as epoch seconds) and `audit_events` (event fields as columns,
   `payload` as jsonb) to Supabase. Realtime would be on, and reviewers could
   only select. Today the gateway does not use Supabase at all, so the app's
   working mode is `READ_SOURCE=api`.
