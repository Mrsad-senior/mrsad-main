import 'package:mirsad/core/config/app_config.dart';

/// The kinds of implementation a repository can be backed by.
enum DataSourceKind { mock, api }

/// The one switch: which implementation backs every repository.
///
/// Decided once at startup from [AppConfig]. `core/di` registers the matching
/// data sources, so nothing else in the app knows where data comes from.
class DataSources {
  const DataSources(this.kind);

  factory DataSources.from(AppConfig config) =>
      DataSources(config.useMock ? DataSourceKind.mock : DataSourceKind.api);

  /// Mock data and mock sign-in, or the Mirsad gateway for everything.
  final DataSourceKind kind;

  bool get usesApi => kind == DataSourceKind.api;
}
