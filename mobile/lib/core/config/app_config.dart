/// Where approvals and events are read from when mocks are off.
enum ReadSource { supabase, api }

/// Build-time settings, supplied with `--dart-define-from-file=env/<name>.json`.
///
/// See `env/example.json` for the keys.
class AppConfig {
  const AppConfig({
    required this.useMock,
    required this.readSource,
    required this.apiBaseUrl,
    required this.supabaseUrl,
    required this.supabaseAnonKey,
  });

  factory AppConfig.fromEnvironment() {
    return AppConfig(
      useMock: const bool.fromEnvironment('USE_MOCK', defaultValue: true),
      readSource: parseReadSource(
        const String.fromEnvironment('READ_SOURCE', defaultValue: 'supabase'),
      ),
      apiBaseUrl: const String.fromEnvironment(
        'API_BASE_URL',
        defaultValue: 'http://10.0.2.2:8000',
      ),
      supabaseUrl: const String.fromEnvironment('SUPABASE_URL'),
      supabaseAnonKey: const String.fromEnvironment('SUPABASE_ANON_KEY'),
    );
  }

  /// When true, every repository uses mock data and sign-in is mocked.
  final bool useMock;

  /// Where reads come from when [useMock] is false. Null if the value in the
  /// env file was not recognised; [validate] reports that.
  final ReadSource? readSource;

  final String apiBaseUrl;
  final String supabaseUrl;
  final String supabaseAnonKey;

  bool get hasSupabase => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;

  /// Returns a developer-facing description of what is wrong with this
  /// configuration, or null when the app can start with it.
  String? validate() {
    if (useMock) return null;
    if (readSource == null) {
      return 'READ_SOURCE must be "supabase" or "api".';
    }
    if (!hasSupabase) {
      return 'USE_MOCK is false, so SUPABASE_URL and SUPABASE_ANON_KEY are '
          'required: reviewers sign in with Supabase Auth.';
    }
    final apiUri = Uri.tryParse(apiBaseUrl);
    if (apiUri == null || !apiUri.hasScheme || apiUri.host.isEmpty) {
      return 'API_BASE_URL must be an absolute URL, got "$apiBaseUrl".';
    }
    return null;
  }

  static ReadSource? parseReadSource(String value) =>
      ReadSource.values.asNameMap()[value.trim().toLowerCase()];
}
