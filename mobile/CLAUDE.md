# Mirsad mobile app

Read this before changing anything in `mobile/`. It records the project brief and the rules every session follows.

## What Mirsad is

Mirsad is a security firewall for AI agents. It sits between an agent and its tools (bank transfers, customer records, email). The Mirsad gateway (a Python FastAPI backend built by other teammates) checks every action the agent tries:

- **allowed**: safe, runs immediately
- **denied**: dangerous, blocked
- **held**: risky, paused until a human approves or rejects it

This app is where that human reviewer works. The demo is in the **finance** sector. Example: a poisoned invoice tricks a banking agent into transferring 50,000 SAR to a new IBAN. Mirsad holds it, and the reviewer rejects it in this app.

This is a university senior project. The current goal is a solid, scalable foundation, not the final UI. Figma designs, Supabase and the hosted API come later, and must plug in without restructuring.

## Repository rules

- The repo root holds `mobile/` (this app) and `docs/`. The gateway code will live elsewhere in the repo.
- **Only modify files inside `mobile/` and `docs/`.** Never write or change backend code.
- When the gateway code is available, read it, and follow the real code wherever it differs from `docs/API_CONTRACT.md` (then update the doc and say what changed).
- Do not commit. After each feature, give the user the exact git commands to commit it.
- Keep `env/dev.json` and `env/prod.json` out of git. Only `env/example.json` is committed.
- Never put a Supabase `service_role` key in the app. Only the anon key belongs here.
- The Supabase project ref is `zrwffxwlyapqgporsobf` (URL `https://zrwffxwlyapqgporsobf.supabase.co`). A Supabase MCP server is configured in `.mcp.json` at the repo root. Use it to read the schema, docs and keys. Do not create tables, run migrations, change RLS or deploy functions through it without the user's explicit OK: the database belongs to the backend team.

## Commands (run from `mobile/`)

```sh
flutter pub get                                        # also regenerates l10n
dart run build_runner build --delete-conflicting-outputs   # after changing a json_serializable model
flutter gen-l10n                                       # after editing an .arb file
flutter analyze                                        # must be clean
flutter test                                           # must pass
flutter run --dart-define-from-file=env/dev.json
```

Generated files (`*.g.dart`, `lib/core/l10n/generated/`) are committed so a fresh clone builds without codegen.

## Architecture

Strict Clean Architecture, feature-first:

```
lib/
  main.dart            bootstrap: config -> DI -> runApp
  app.dart             MaterialApp.router, themes, locales
  core/
    config/            AppConfig (dart-defines) and DataSources (the one switch)
    di/                get_it registration, one module file per feature
    network/           Dio client, auth interceptor, Dio/Supabase error mapping, polling
    errors/            AppException (data layer), Failure (domain), guard helpers
    router/            GoRouter, route paths, bottom-nav shell
    theme/             design tokens (colors, typography, spacing, radii), light + dark
    l10n/              ARB files (en, ar), generated code, locale cubit, label helpers
    widgets/           shared widgets: status badge, risk chip, empty/error/loading states
    utils/             Clock
  features/<feature>/
    domain/            entities, repository interfaces, use cases
    data/              models (json_serializable), data sources, repository implementations
    presentation/      cubits + states, pages, widgets
```

Features: `auth`, `approvals`, `activity`, `audit`.

### Layer rules

- **domain** is pure Dart: no Flutter, Dio, Supabase or json_annotation imports, and no imports from `data/` or `presentation/`. `test/architecture_test.dart` enforces this.
- **data** sources throw `AppException` subtypes (`core/errors/exceptions.dart`). Repository implementations catch them with `guard` / `guardStream` and return `Either<Failure, T>` (fpdart).
- **presentation** never sees an exception. Cubits receive `Either` values and expose state. Pages show failures through `failure.localizedMessage(l10n)`.
- Features do not import each other. Only the composition roots (`core/di`, `core/router`, `app.dart`, `main.dart`) know about every feature.
- Use cases are small classes with a `call` method. Cubits depend on use cases, not repositories.
- Pages read their cubit from context. The router creates cubits (`BlocProvider(create: (_) => getIt<...>())`), so widget tests can provide a mock cubit.
- Widgets get the current time from `context.read<Clock>()`, never `DateTime.now()` directly, so countdowns are testable.

### Data sources

Every repository is backed by one of three implementations:

1. **Mock**: realistic fake finance data, used now.
2. **API**: the Mirsad gateway over Dio (`docs/API_CONTRACT.md`).
3. **Supabase**: reads tables and listens to realtime changes.

The plan: reviewers sign in with Supabase Auth. The app **reads** approvals and events from Supabase (realtime, so new held actions appear instantly) and **sends** decisions through the gateway API, because the gateway must resume or cancel the agent's action.

`core/config/data_sources.dart` is the one switch:

| Setting                            | Reads (approvals, events) | Gateway (decisions, audit) | Auth     |
|------------------------------------|---------------------------|----------------------------|----------|
| `USE_MOCK=true`                    | mock                      | mock                       | mock     |
| `USE_MOCK=false`, `READ_SOURCE=supabase` | Supabase            | API                        | Supabase |
| `USE_MOCK=false`, `READ_SOURCE=api`      | API                 | API                        | Supabase |

Audit has no Supabase source (verifying the hash chain is the gateway's job). Auth has no API source (sign-in is Supabase Auth). The API client sends the Supabase access token as `Authorization: Bearer <token>`.

### Environment config

Builds read `--dart-define-from-file=env/<name>.json`:

| Key                 | Meaning                                                       |
|---------------------|---------------------------------------------------------------|
| `USE_MOCK`          | `true` uses mock data and mock sign-in everywhere             |
| `READ_SOURCE`       | `supabase` or `api`; where reads come from when not mocking   |
| `API_BASE_URL`      | Gateway URL. Dev: `http://10.0.2.2:8000` (Android emulator). Prod: `https://api.<our-domain>` later |
| `SUPABASE_URL`      | Supabase project URL                                          |
| `SUPABASE_ANON_KEY` | Supabase anon key, or the newer "publishable" key (never the service_role / secret key) |

Without a file the app defaults to `USE_MOCK=true`. When mocks are off, a missing Supabase config shows a configuration error screen instead of crashing.

## Domain model (from the brief)

**Approval**: `id`, `agent_id`, `sector` (finance | healthcare | general), `tool`, `arguments` (map), `status` (held | approved | rejected | expired), `risk_score` (0-1), `tainted` (bool), `user_task` (the user's original request), `reasons` (list of `{layer: policy | taint | intent | llm_judge | keywords, message}`), `created_at`, `expires_at`.

**Event**: `id`, `agent_id`, `tool`, `decision` (allowed | denied | held), `summary`, `risk_score`, `created_at`.

**Audit**: `{valid: bool, broken_at: int?}`.

Held actions auto-reject after 5 minutes. The gateway does the auto-reject; the app only shows the countdown from `expires_at`.

## Mock data (finance, fake only)

- Held: `transfer_funds` 50,000 SAR to a new IBAN after reading an invoice; user task "Process this supplier invoice"; reasons from `intent` and `llm_judge`.
- Held: `send_email` with a customer statement to an external address.
- Denied: Arabic prompt injection in an email trying to export customer records.
- Denied: English injection trying to change a beneficiary.
- Allowed: balance lookups, internal emails.

Use `.example` domains and obviously fake IBANs and names. Pull to refresh on an empty mock approvals list brings the demo approvals back.

## Screens

1. Sign in (mock auth for now).
2. Pending approvals: tool, amount/recipient if present, risk badge, countdown to auto-reject, pull to refresh.
3. Approval details: the user's original task vs what the agent is trying to do, arguments, each layer's reason, Approve / Reject with confirmation and an optional note.
4. Activity feed: decisions colour-coded allowed / denied / held, filterable.
5. Audit status: chain valid, or broken at entry N.

Bottom navigation: Approvals, Activity, Audit.

## UI rules

- All colors, text styles, spacing and radii come from `core/theme/`. Never hard-code a color or a magic number in a widget. Status colors come from the `MirsadColors` theme extension (`context.statusColors`). Figma styles will replace the token values, not the widgets.
- All user-facing text comes from the ARB files in `core/l10n/arb/`, in both English and Arabic. Add the key to both files.
- RTL from day one: use `EdgeInsetsDirectional`, `AlignmentDirectional`, `start`/`end`, never `left`/`right`.
- Shared widgets live in `core/widgets/`; feature-only widgets stay in the feature.
- Figma: a Figma MCP server is configured in `.mcp.json` at the repo root. It works from links to a frame or layer ("Copy link to selection"). When building from a design, first pull its variables and styles (`get_variable_defs`) into `core/theme/tokens/`, then build the widgets against the tokens. Copy text goes into both ARB files. The Figma file also has website screens; ignore them here.

## Quality bar

- Unit tests for every use case, repository and cubit (`bloc_test`, `mocktail`). The approval details page has a widget test.
- `flutter analyze` is clean and `flutter test` passes before a feature is finished.
- Follow Effective Dart. Keep files small: one public class per file, split widgets when a build method grows.
- Tests mirror `lib/` under `test/`. Shared test helpers live in `test/helpers/`.

## Adding a feature or screen

1. `domain/`: entity, repository interface, one use case per action.
2. `data/`: model with `fromJson`/`toEntity`, a data source interface plus mock / API / Supabase implementations, the repository implementation wrapping calls in `guard` / `guardStream`.
3. `presentation/`: cubit + `part` state file (Equatable, explicit status enum), page, widgets.
4. Register it in `core/di/<feature>_module.dart`; pick the data source with a `switch` on `DataSources`.
5. Add the route in `core/router/app_router.dart`, creating the cubit there.
6. Add every string to both `app_en.arb` and `app_ar.arb`, then `flutter gen-l10n`.
7. Tests under `test/features/<feature>/`, with mocks in `<feature>_mocks.dart` and fixtures in `<feature>_fixtures.dart`.

## Conventions and gotchas

- Toolchain: Flutter 3.44, Dart 3.12. Material lives in the `material_ui` package; still import `package:flutter/material.dart`. Component themes use the `*ThemeData` classes (`AppBarThemeData`, `CardThemeData`, `InputDecorationThemeData`).
- Private named constructor parameters are allowed and the lint prefers them: `Foo({required this._bar})`, called as `Foo(bar: ...)`.
- `Supabase.initialize` takes `publishableKey:` (`anonKey:` is deprecated).
- Live lists are streams: repositories expose `watch...()` plus a `refresh...()` that pushes onto the same stream. The API sources poll with `core/network/polling_stream.dart`; Supabase uses realtime.
- A data source implementing both reads and decisions (mock, API) refreshes its own pending list after a decision; the repository does not.
- Tests: `test/helpers/pump_app.dart` (theme, l10n, fake clock), `fake_http_adapter.dart` (real Dio against canned responses), `either.dart` (`rightOf`). `test/architecture_test.dart` enforces the layer rules; `test/app_smoke_test.dart` boots the real app in mock mode.
- Android debug builds allow plain HTTP only to `10.0.2.2` / `localhost` (`android/app/src/debug/res/xml/network_security_config.xml`). Release builds are HTTPS only.

## Packages

flutter_bloc, go_router, dio, get_it, equatable, fpdart, json_annotation, json_serializable, build_runner, intl, flutter_localizations, supabase_flutter. Dev only: bloc_test, mocktail. Ask before adding anything else.

## Open items

- As of 2026-10-29 the gateway code was not in this repository. `docs/API_CONTRACT.md` is written from the brief. Reconcile it with the real gateway once it is available.
- The chosen language is not persisted between launches (it would need `shared_preferences`).
- A gateway `401` shows "session expired" but does not sign the reviewer out automatically yet.
- iOS: talking to a local `http://` gateway from the simulator needs an App Transport Security exception; not set up.
