# Mirsad reviewer app

Flutter app where a human reviewer approves or rejects the agent actions the Mirsad gateway holds. Arabic and English, light and dark.

## Run it

```sh
cd mobile
cp env/example.json env/dev.json        # once; dev.json stays out of git
flutter pub get
flutter run --dart-define-from-file=env/dev.json
```

`env/example.json` has `USE_MOCK: true`, so the app runs on fake finance data with mock sign-in: any email and a password of 6 or more characters.

To talk to a gateway on your machine from the Android emulator, set `USE_MOCK` to `false`, `READ_SOURCE` to `api`, keep `API_BASE_URL` at `http://10.0.2.2:8000`, and fill in `SUPABASE_URL` and `SUPABASE_ANON_KEY` (sign-in always uses Supabase Auth when mocks are off).

## Check it

```sh
flutter analyze
flutter test
```

After changing a model: `dart run build_runner build --delete-conflicting-outputs`.
After changing an `.arb` file: `flutter gen-l10n`.

## Where things are

- `CLAUDE.md`: the project brief, architecture rules and conventions. Read it first.
- `../docs/API_CONTRACT.md`: the endpoints and JSON the app expects from the gateway.
- `lib/core/config/data_sources.dart`: the switch between mock, API and Supabase data.
- `lib/core/theme/tokens/`: every color, text style, spacing and radius.
- `lib/core/l10n/arb/`: English and Arabic strings.
