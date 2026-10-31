import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/config/data_sources.dart';

AppConfig _config({required bool useMock, ReadSource? readSource}) {
  return AppConfig(
    useMock: useMock,
    readSource: readSource,
    apiBaseUrl: 'http://10.0.2.2:8000',
    supabaseUrl: 'https://project.supabase.co',
    supabaseAnonKey: 'anon-key',
  );
}

void main() {
  test('mock mode mocks everything', () {
    final sources = DataSources.from(_config(useMock: true));
    expect(sources.reads, DataSourceKind.mock);
    expect(sources.gateway, DataSourceKind.mock);
    expect(sources.auth, DataSourceKind.mock);
    expect(sources.usesApi, isFalse);
    expect(sources.usesSupabase, isFalse);
  });

  test('Supabase reads still send decisions through the API', () {
    final sources = DataSources.from(
      _config(useMock: false, readSource: ReadSource.supabase),
    );
    expect(sources.reads, DataSourceKind.supabase);
    expect(sources.gateway, DataSourceKind.api);
    expect(sources.auth, DataSourceKind.supabase);
  });

  test('API reads use the gateway for everything but sign-in', () {
    final sources = DataSources.from(
      _config(useMock: false, readSource: ReadSource.api),
    );
    expect(sources.reads, DataSourceKind.api);
    expect(sources.gateway, DataSourceKind.api);
    expect(sources.auth, DataSourceKind.supabase);
  });
}
