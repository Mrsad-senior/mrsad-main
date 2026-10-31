import 'package:mirsad/core/config/app_config.dart';

/// The kinds of implementation a repository can be backed by.
enum DataSourceKind { mock, api, supabase }

/// The one switch: which implementation backs each group of repositories.
///
/// Decided once at startup from [AppConfig]. `core/di` registers the matching
/// data sources, so nothing else in the app knows where data comes from.
class DataSources {
  const DataSources({
    required this.reads,
    required this.gateway,
    required this.auth,
  });

  factory DataSources.from(AppConfig config) {
    if (config.useMock) {
      return const DataSources(
        reads: DataSourceKind.mock,
        gateway: DataSourceKind.mock,
        auth: DataSourceKind.mock,
      );
    }
    return DataSources(
      reads: config.readSource == ReadSource.api
          ? DataSourceKind.api
          : DataSourceKind.supabase,
      gateway: DataSourceKind.api,
      auth: DataSourceKind.supabase,
    );
  }

  /// Pending approvals and the activity feed: mock, API or Supabase.
  final DataSourceKind reads;

  /// Things only the gateway can do (approve / reject, verify the audit
  /// chain): mock or API.
  final DataSourceKind gateway;

  /// Reviewer sign-in: mock or Supabase.
  final DataSourceKind auth;

  bool get usesSupabase =>
      reads == DataSourceKind.supabase || auth == DataSourceKind.supabase;

  bool get usesApi =>
      reads == DataSourceKind.api || gateway == DataSourceKind.api;
}
