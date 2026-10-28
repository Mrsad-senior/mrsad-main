# Mirsad web UI: admin dashboard and approver PWA

Mirsad ships two browser front ends from one React 18 + TypeScript + Vite code base in `web/`:

| App | URL | Who uses it | Entry |
|---|---|---|---|
| Admin dashboard | `/` | administrators, auditors, approvers at a desk | `web/index.html` → `web/src/dashboard/` |
| Approver PWA | `/approve` | approvers on a phone (installable) | `web/approve.html` → `web/src/approver/` |

Both talk only to the REST API of the gateway (`/api/...`, see `docs/api.md`) and share one layer in
`web/src/shared/` (API client, live stream, i18n, styles, components). `npm run build` writes the static
files to `src/mirsad/static/`, which FastAPI serves (`src/mirsad/api/static.py`): `/` and any unknown
path return the dashboard, `/approve` returns the PWA, `/assets/*` holds the hashed bundles and
`/approve-sw.js` is the service worker. No CDN, no inline scripts, no `data:` URIs: everything is
same-origin so the strict CSP set by the API (`script-src 'self'`) holds.

## Building, running and testing

```bash
cd web
npm ci                     # Node >= 20.19 (developed on Node 24)
npm run dev                # Vite on :5173, proxies /api, /v1, /healthz to MIRSAD_API (default http://127.0.0.1:8700)
npm test                   # vitest + jsdom (194 tests)
npm run typecheck          # tsc --noEmit (strict)
npm run build              # typecheck, vite build -> ../src/mirsad/static, then a size report
```

`npm run build` ends with `scripts/report-sizes.mjs`, which lists every emitted file (raw and gzip) and
the initial payload of each page. Current numbers (gzip, level 9):

| | Initial payload | Notes |
|---|---|---|
| Dashboard `/` | 102 kB (326 kB raw), 7 files | React 45 kB, shared layer 36 kB, shell 11 kB, CSS 10 kB |
| Approver `/approve` | 94 kB (300 kB raw), 7 files | never loads the charts chunk |
| Charts (Recharts) | 112 kB, lazy | only when the Overview page is opened |
| Each other dashboard page | 1–5 kB, lazy | one chunk per page |

The size budgets in the script (120 kB / 105 kB gzip) are advisory: going over prints a warning so growth
gets noticed; it does not fail the build. Most of the shared chunk is the two dictionaries (about 600
strings each), which both apps need for the language toggle.

Tests (`web/tests/`):

* `client.test.ts`, `backend.test.ts`: the API client against the request/response shapes of the
  implemented routers (which extend BUILD_SPEC section 8; see "Backend alignment" below).
* `contract.test.tsx`: an approval record and a `tool_call.decision` audit event captured from a running
  server, pushed through the same parsing and rendering code the UI uses.
* `ui.test.tsx`: component flows on a fake backend: approver list → detail → approve with confirmation
  and note, Web Push deep link, Arabic/RTL rendering, Demo console scenario loading and chat, user creation
  with a server-generated password, password rules, policy rollback.
* `sse.test.ts`, `spans.test.ts`, `lib.test.ts`, `countdown.test.ts`: the stream parser and reconnect
  logic, detector-span highlighting (code-point offsets, Arabic, emoji, combining marks), provenance,
  diff, formatting.
* `i18n.test.ts`: both dictionaries have identical keys and placeholders, Arabic values are really
  Arabic, every key referenced in the code exists, every audit event type has a label.
* `contrast.test.ts`: WCAG AA contrast for every foreground/background token pair in light and dark mode.

Test data is neutral: placeholder strings such as `SAMPLE-FLAGGED-TEXT`, fictional Najd Trading Co.
business text and addresses on the reserved `.example` TLD. The UI and its tests contain no attack
payloads.

### Smoke test against a real server

```bash
export MIRSAD_DATA_DIR=$(mktemp -d) MIRSAD_ENABLE_DEMO=true
python -m mirsad.cli init --demo          # writes $MIRSAD_DATA_DIR/credentials.txt (mode 600)
python -m mirsad.cli serve --port 8711 --demo
```

Then sign in through `POST /api/auth/login` with the generated credentials and fetch `/`, `/approve`,
`/approve-sw.js`, the `/assets/*` files referenced by the two HTML pages and the API endpoints the pages
use. On 2026-10-11 a scripted run of 92 such checks passed, including a full approval round trip: an
agent (guard API, demo agent key) reads an e-mail, then tries to e-mail an outside address; the call is
paused, the approver's SSE stream receives `approval.requested`, the approver denies it with a note, the
waiting agent call returns `deny` (`DENIED_BY_HUMAN`), a second decision gets 409, and the audit trail of
that call can be filtered, replayed (match), verified and exported. Both pages were also opened in a
browser: they boot without console errors and switch to Arabic right-to-left.

## Dashboard, page by page

The sidebar only shows pages the signed-in role may use; the same role check guards each route, and the
API remains the authority (403 is shown as "You do not have permission").

| Page | Roles | API used |
|---|---|---|
| Overview | all | `GET /api/stats/overview`, `GET /api/stats/timeseries`, `POST /api/audit/verify` |
| Activity & audit | admin, auditor | `GET /api/audit/events[/{seq}]`, `POST .../replay`, `POST /api/audit/verify`, `GET /api/audit/export` |
| Approvals | admin, approver | `GET /api/approvals[/{id}]`, `POST /api/approvals/{id}/decision` |
| Policies | admin (edit), auditor (read) | `GET /api/policies[/{version}]`, `POST /api/policies/validate`, `PUT /api/policies`, `POST /api/policies/{version}/activate` |
| Agents | admin | `GET/POST /api/agents`, `PATCH/DELETE /api/agents/{id}`, `POST /api/agents/{id}/rotate-key` |
| Users | admin | `GET/POST /api/users`, `PATCH/DELETE /api/users/{username}` |
| Tools | admin, auditor | `GET /api/tools` |
| Detector playground | all | `POST /api/detector/scan`, `/assets/playground-samples.json` |
| Demo console | all (demo mode only) | `GET /api/demo/scenarios`, `POST /api/demo/scenarios/{id}/apply`, `POST /api/demo/chat`, `GET /api/demo/state`, `POST /api/demo/reset` |
| Settings | all | `GET /healthz` |

**Sign in.** Username and password; a 429 from the login throttle is shown as "too many attempts". The
JWT is kept in memory and in `sessionStorage` (a reload keeps the session, closing the tab ends it). Any
401 signs the user out everywhere in the page.

**Overview.** Key figures for the last hour, 24 hours or 7 days: tool calls, allowed, denied, sent for
approval, waiting for approval, injections detected, results sanitized and blocked, median and 95th
percentile gateway overhead (excluding human wait). A line chart shows decisions and injection detections
over time, a table shows decisions per tool with a stacked bar, and a bar chart shows which defence layer
raised objections. Every chart has a "Show table" toggle with the same numbers. The audit card shows
whether the HMAC hash chain is intact and lets admins and auditors re-verify it. The page refreshes on
live events (at most every 5 s) and every 30 s.

**Activity & audit log.** A paged table of every audit event (sequence number, time, type, agent, tool,
outcome, risk). Filters: free text, agent, tool, outcome (decision or inspection outcomes), event type,
session, call id and a time range; they live in the URL (`#/activity?tool=send_email&offset=50`) so a view
can be shared. A banner offers to load new events as they stream in. The header verifies the whole chain
and exports the current filter as JSON or CSV. Clicking a row opens a drawer with:

* the summary (time, outcome, risk and risk score, agent, tool, destination, session, call id, policy
  version, a "monitor mode: not enforced" tag when applicable);
* the reasons table: layer, code, bilingual explanation, effect, risk score and the raw evidence;
* for inspections, the detector result (score gauge, label, language, model and rule scores, obfuscation
  signals) and the stored content with detected spans highlighted;
* taint provenance: which earlier tool call and field each flagged value came from, plus the session's
  taint state (untrusted sources, tracked values, whether an injection was seen);
* the arguments, with the ones that carry outside data flagged;
* the previous hash and hash (copyable) and the raw event as collapsible JSON;
* actions: **Replay** (re-evaluates the stored decision or inspection with the policy version it
  recorded and says whether the result matches), **Verify chain**, **Export event**, and **All events of
  this call / session**, which filters the list to trace one call from decision to approval to inspection.

**Approvals.** The live pending queue (soonest expiry first) with risk colour, countdown bar,
plain-language summary and Review / Deny / Approve buttons, and the decision history with a status
filter. Review opens the same explanation the approver app shows. Deciding always goes through a
confirmation dialog that restates the action and takes an optional note. A 409 ("already decided or
expired") is reported without an error page. Without a live stream the queue polls every 15 s.

**Policies.** The active YAML in an accessible plain-textarea editor with line numbers (Tab inserts two
spaces; Esc then Tab leaves the editor). Validate shows the server's errors, with "go to line" links when an error names a line;
Activate validates again, shows a diff against the active version and asks for a change note. Monitor mode
(`mode: monitor`) is flagged in the editor and after activation. The version history lists every stored
version; each can be viewed, compared with the editor, loaded into the editor, or (admins) re-activated
as a rollback after confirmation. Auditors get a read-only view.

**Agents.** Agent identities with policy agent, key prefix, last seen and status; create, rotate key,
disable/enable and delete (with confirmation). The id field follows the server's slug rule. A new or
rotated key is shown exactly once in a dialog that cannot be dismissed until "I have stored this key" is
ticked; server warnings (for example a policy agent id that the active policy does not define, whose calls
would all be denied) are shown in the same dialog.

**Users.** People who can sign in, with an explanation of the three roles. Inline role change and
enable/disable (not for your own account), an Edit dialog for display name, language and password reset,
and delete with confirmation. New users get a server-generated strong password by default, shown once in
an acknowledge-to-close dialog; an admin can type one instead (at least 10 characters, the server's
rule). Usernames follow the server's pattern (3–64 characters, letters, digits and `. _ @ -`, starting
with a letter or digit).

**Tools.** Upstream tools discovered by the gateway and, per policy agent, how the active policy treats
each one: allowed, trust of its results, sensitivity, where it sends data (and which arguments decide
that), risk, approval mode, and whether results are scanned. The input schema is available per tool.

**Detector playground.** Paste Arabic, English or mixed text and scan it: score gauge with the flag and
block thresholds, verdict, detected language, model and rule scores, latency, highlighted evidence spans
(with the rule that matched) and obfuscation signals. The built-in sample buttons are ordinary Najd
Trading Co. business texts in English, Arabic and mixed language; they show what a benign verdict looks
like and that Arabic text, Arabic-Indic digits and code-switching are handled. Teams that want labelled
evaluation texts in the playground put them in a deployment file instead of the code:

* source copy `web/public/assets/playground-samples.json` (copied into every build), deployed copy
  `src/mirsad/static/assets/playground-samples.json` (served at `/assets/playground-samples.json`, editable
  without rebuilding);
* format `{"samples": [{"id": "...", "label_en": "...", "label_ar": "...", "lang": "en|ar|mixed", "text": "..."}]}`;
  at most 24 entries, labels cut to 60 characters and texts to 100 000 (the scan endpoint's limit);
* the file ships with an empty list; when it has entries they appear as a second row of "Team samples"
  buttons. A missing or malformed file is ignored.

**Demo console** (only when the server runs with `MIRSAD_ENABLE_DEMO=true`; otherwise the page says how
to enable it). A chat with the demo agent in the simulated Najd Trading Co. workspace:

* the **Mirsad protection** switch runs the agent through the gateway (on) or directly against the tools
  (off, with a warning banner);
* **Load scenario** calls `POST /api/demo/scenarios/{id}/apply`, which resets the workspace and plants
  the scenario's untrusted content, then fills in the scenario's harmless user request in the UI language.
  The page shows the scenario title and the server's one-line description of what the planted content
  tries to make the agent do; it never displays the planted content itself;
* each reply shows the tool-call timeline of that turn (tool, Mirsad's decision and inspection, the
  deciding reason, arguments, result preview) and a note when the agent stopped at its step limit;
* the **attacker inbox** lists everything that left the organisation (e-mails to outside recipients with
  subject and body preview, web requests to outside domains);
* **Workspace changes** counts e-mails sent, web requests, customer exports, deleted records, money
  transfers and CRM note changes, so destructive actions are visible even when nothing leaked;
* **Reset demo** restores the workspace and clears the conversation.

**Settings.** Theme (system, light, dark), language and, in Arabic, Western or Arabic-Indic digits;
desktop notifications for new approvals while the tab is in the background; a link to the approver app;
account details and sign out; server health and version.

## Approver PWA

A single-screen app designed for a decision in under 30 seconds on a phone.

* **Pending list.** One large card per request (the whole card is the touch target): risk shown by
  stripe colour, icon and text label, a live countdown, the tool and agent, the plain-language summary in
  the user's language, and how long ago it arrived. Soonest expiry first. A History tab lists decided,
  expired and cancelled requests with who decided.
* **Detail.** Risk badge, tool, agent and time, countdown bar, then three sections:
  *What the agent wants to do* (the server's EN/AR summary), *Why Mirsad paused it* (only the reasons that
  caused the pause, in plain language, with the layer that raised each) and *Where the data came from*
  (source tool, call id and field of each flagged value, with trust and sensitivity), followed by the
  arguments (collapsed, long values expandable, arguments carrying outside data flagged).
* **Approve / Deny.** Two large buttons; each opens a bottom sheet that restates the consequence and
  takes an optional note before anything is sent. Buttons are disabled when the request has expired or the
  phone is offline. If someone else decided first, the app says so.
* **Live updates.** One SSE connection per page (`GET /api/stream`) adds new requests and removes decided
  ones instantly; while the stream is down the list polls every 20 s and refreshes when it reconnects. New
  requests are announced to screen readers.
* **Notifications.** With permission, a system notification appears for each new request while the app
  is in the background (Notification API through the service worker). When the server has VAPID keys
  (`MIRSAD_VAPID_PUBLIC_KEY`, `MIRSAD_VAPID_PRIVATE_KEY`), the app also subscribes to Web Push, so alerts
  arrive while the app is closed. Notifications use the language chosen in the app (the server sends
  `title`/`title_ar` and `body`/`body_ar`) and open the request directly. Deep links `#/a/<id>` and the
  server's `#/approvals/<id>` both work. Signing out from the menu first removes this device's push
  subscription, so a shared phone stops receiving the previous user's alerts.
* **Offline.** The service worker precaches the app shell (the exact files of the approver entry,
  computed at build time) and keeps the last approval list for offline viewing; decisions need a
  connection. Cached approval data is deleted on sign-out. `/api/stream` and every non-GET request bypass
  the worker.
* **Manifest.** `/assets/manifest.webmanifest`: bilingual name, `start_url` and `scope` `/approve`,
  standalone display, portrait, theme colour, 192/512 px and maskable icons, apple-touch icon.
* **Menu.** Theme, language, notification status, link to the dashboard, sign out.

### Installing the approver app

The app must be served over HTTPS (browsers allow service workers and push only on secure origins;
`http://localhost` is the exception used in development).

**Android (Chrome, Edge, Samsung Internet)**

1. Open `https://<your-mirsad-host>/approve` and sign in.
2. Tap **Install** on the "Install Mirsad Approver" card (or browser menu ⋮ → **Install app** /
   **Add to Home screen**).
3. Open Mirsad from the home screen and tap **Turn on alerts**, then allow notifications.

**iPhone / iPad (Safari, iOS/iPadOS 16.4 or later for alerts)**

1. Open `https://<your-mirsad-host>/approve` in Safari and sign in.
2. Tap **Share** → **Add to Home Screen** → **Add** (the app shows these steps on iOS).
3. Open Mirsad from the home screen (not from Safari), tap **Turn on alerts** and allow notifications.
   On iOS, web notifications only work for apps added to the home screen.

The session ends when the app's tab or window is closed (token in session storage), so approvers sign in
again after the app has been fully closed. This is deliberate for a security tool on mobile devices.

## Accessibility

* Semantic structure: landmarks (`header`, `nav`, `main`, `aside`), one `h1` per page, tables with
  `scope`d headers and captions where needed, lists for lists, `dl` for key/value data, a skip link.
* Every control has a visible or programmatic label; inputs are tied to hints and errors with
  `aria-describedby`/`aria-invalid`; busy buttons use `aria-busy`.
* Keyboard: everything is reachable and operable by keyboard with a visible focus ring; tabs follow the
  WAI-ARIA pattern (arrow keys, mirrored in RTL); dialogs are native `<dialog>` with `showModal()` (focus
  trap, Esc, focus returned to the opener); after navigation focus moves to the new page heading; the
  policy editor never traps focus (Esc then Tab).
* Live regions announce new approval requests, chain verification and replay results, and paging changes.
* Colour is never the only signal: risk, decisions and statuses always have an icon and a text label.
  WCAG AA contrast for all token pairs in both themes is enforced by a test.
* Charts have text alternatives and a table view with the same data.
* `prefers-reduced-motion` disables animations and chart transitions; `prefers-color-scheme` picks the
  theme unless the user chose one.
* Touch targets in the approver app are at least 44 × 44 px; layouts are responsive down to phone width
  (the dashboard sidebar becomes a menu).

## Bilingual design (English / Arabic)

* Every UI string exists in `web/src/shared/i18n/en.ts` and `ar.ts` (Modern Standard Arabic), with the
  same keys and placeholders (enforced by the type system and by tests). The language toggle is on every
  screen. The interface starts in the browser's language; at sign-in it switches to the language saved
  for the user on the server, unless a language was already chosen on this device, which always wins.
* Switching to Arabic sets `<html lang="ar" dir="rtl">`. Layout uses CSS logical properties
  (`margin-inline-start`, `inset-inline-end`, ...), so the whole interface mirrors without separate
  stylesheets; directional icons (arrows, chevrons) flip, and charts mirror their axes.
* Mixed content is isolated: user and agent text uses `dir="auto"`, identifiers (tool names, e-mail
  addresses, hashes, YAML, JSON) stay left-to-right inside `<bdi>` or `dir="ltr"`, so an English address
  inside an Arabic sentence renders correctly.
* Messages that come from the server are bilingual at the source: reasons carry `message_ar`, approvals
  carry `summary_ar`, push payloads carry `title_ar`/`body_ar`, scenarios carry Arabic titles, prompts and
  descriptions. The UI shows the Arabic version when the interface is Arabic and falls back to English.
* Dates use the Gregorian calendar in both languages (so audit times match exports); numbers can use
  Western or Arabic-Indic digits.
* Detector spans are reported by Python in Unicode code points; the highlighter slices by code point, so
  Arabic diacritics, emoji and mixed scripts are highlighted exactly.

## Security notes for the front end

* No token in URLs: the SSE stream is read with `fetch` and an `Authorization` header (the native
  `EventSource` cannot send headers), so tokens never reach access logs or history.
* Strict same-origin CSP compatible: no inline script, no third-party resources, no `data:` assets.
* Agent keys and generated passwords are displayed once and never stored by the UI.
* All text from agents, tools and tool results is rendered as text (React escaping), never as HTML.
* The playground and demo pages never embed attack content; the demo shows only the server's abstract
  description of a scenario.

## Backend alignment

The UI follows the routers as implemented, which extend BUILD_SPEC section 8 in these places:
`expires_in` in the login response; `results_blocked`, `results_inspected` and `audit_head_seq` in the
overview; `call_id` and `order` audit filters; the JSON export is an envelope
`{format, exported_at, filters, head, events}`; `POST /api/policies/{version}/activate` (rollback) and the
activation result's `previous_version`, `mode` and `agents`; `warnings` when creating an agent;
`generated_password` when creating a user without a password; `enabled` in `GET /api/push/vapid` and
`POST /api/push/unsubscribe`; `POST /api/demo/scenarios/{id}/apply`, scenario fields `title_en/_ar`,
`user_prompt_en/_ar`, `expected_attack`; `protected` and `stopped_reason` in demo chat replies; the
`attacker_inbox` item shape; the demo chat request rejects unknown fields; audit event types
`auth.login`, `agent.updated`, `agent.deleted`, `user.updated` and `user.deleted`; taint evidence uses
`source_trust`/`source_sensitivity`; the SSE stream sends a `ready` event and gives approvers audit
summaries without payloads.

## Why a PWA instead of a Flutter app

* **One code base.** The approver shares the API client, live-stream reader, i18n dictionaries,
  explanation components and design tokens with the dashboard. A Flutter app would duplicate all of that
  in Dart and drift from the dashboard with every API change.
* **No store cost or review.** No Apple developer fee, no Play Console account, no review delay before a
  security fix reaches approvers; the gateway serves the app, so it is always the version that matches the
  API.
* **Installable on both platforms.** Android and iOS (16.4+) install it to the home screen, run it
  full-screen and deliver Web Push notifications; desktop browsers can install it too.
* **Testable here.** It is built and tested with the same `npm test` / `npm run build` as the dashboard,
  in CI and on any laptop, without Xcode, the Android SDK or device emulators, and the gateway's own
  smoke test covers it.
* **Small.** About 94 kB gzip on first load, then served from the cache.

Limits of the PWA approach: on iOS, notifications need the app on the home screen and iOS 16.4 or later;
Web Push needs VAPID keys and HTTPS; there is no background execution beyond the service worker; and
there is no biometric confirmation step.

**Future work.** Wrap the same build in Capacitor (or rebuild the approver in Flutter) for store
distribution where an organisation requires managed apps, native push through FCM/APNs, and a biometric
or device-PIN confirmation before an approval is sent. The API and the decision flow would not change.

## Known limitations

* The UI has no automated end-to-end browser tests (Playwright or similar); flows are covered by jsdom
  component tests, captured-response contract tests and the manual/scripted smoke test above.
* Web Push was verified up to subscription handling in code and tests; delivery to real phones was not
  tested here (it needs HTTPS, VAPID keys and a device).
* Re-activating a policy whose YAML only differs in comments keeps the same version (versions hash the
  normalised YAML); the UI then reports that version as active again.
