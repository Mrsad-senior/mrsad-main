# Mirsad reviewer app

Flutter app where a human reviewer approves or rejects the agent actions the Mirsad gateway holds. Arabic and English, light and dark.

## Run it

```sh
cd mobile
cp env/example.json env/dev.json        # once; dev.json stays out of git
flutter pub get
flutter run --dart-define-from-file=env/dev.json
```

`env/example.json` has `USE_MOCK: true`, so the app runs on fake finance data with mock sign-in: any username and a password of 6 or more characters.

To talk to a gateway, set `USE_MOCK` to `false` and `API_BASE_URL` to the gateway: `http://10.0.2.2:8700` for a gateway on your machine from the Android emulator, or `https://api.mirsad-app.com` for the hosted one. Reviewers then sign in with a gateway account (e.g. `mirsad user create noura@bank.example --role approver`).

## Check it

```sh
flutter analyze
flutter test
```

After changing a model: `dart run build_runner build --delete-conflicting-outputs`.
After changing an `.arb` file: `flutter gen-l10n`.

## Where things are

- `CLAUDE.md`: the project brief, architecture rules and conventions. Read it first.
- `../docs/API_CONTRACT.md`: which gateway endpoints the app calls (see `../docs/api.md` for the full API) and what it still needs.
- `lib/core/config/data_sources.dart`: the switch between mock and gateway data.
- `lib/core/theme/tokens/`: every color, text style, spacing and radius.
- `lib/core/l10n/arb/`: English and Arabic strings.
