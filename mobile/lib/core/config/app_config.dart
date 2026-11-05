/// Build-time settings, supplied with `--dart-define-from-file=env/<name>.json`.
///
/// See `env/example.json` for the keys.
class AppConfig {
  const AppConfig({required this.useMock, required this.apiBaseUrl});

  factory AppConfig.fromEnvironment() {
    return const AppConfig(
      useMock: bool.fromEnvironment('USE_MOCK', defaultValue: true),
      apiBaseUrl: String.fromEnvironment(
        'API_BASE_URL',
        defaultValue: 'http://10.0.2.2:8700',
      ),
    );
  }

  /// When true, every repository uses mock data and sign-in is mocked.
  /// Otherwise everything goes through the gateway at [apiBaseUrl].
  final bool useMock;

  final String apiBaseUrl;

  /// Returns a developer-facing description of what is wrong with this
  /// configuration, or null when the app can start with it.
  String? validate() {
    if (useMock) return null;
    final apiUri = Uri.tryParse(apiBaseUrl);
    if (apiUri == null || !apiUri.hasScheme || apiUri.host.isEmpty) {
      return 'API_BASE_URL must be an absolute URL, got "$apiBaseUrl".';
    }
    return null;
  }
}
