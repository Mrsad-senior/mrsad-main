import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/config/data_sources.dart';

void main() {
  const url = 'http://10.0.2.2:8700';

  test('mock mode mocks everything', () {
    final sources = DataSources.from(
      const AppConfig(useMock: true, apiBaseUrl: url),
    );
    expect(sources.kind, DataSourceKind.mock);
    expect(sources.usesApi, isFalse);
  });

  test('otherwise everything goes through the gateway, sign-in included', () {
    final sources = DataSources.from(
      const AppConfig(useMock: false, apiBaseUrl: url),
    );
    expect(sources.kind, DataSourceKind.api);
    expect(sources.usesApi, isTrue);
  });
}
