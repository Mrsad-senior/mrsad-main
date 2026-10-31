import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/config/app_config.dart';

AppConfig _config({
  bool useMock = false,
  ReadSource? readSource = ReadSource.supabase,
  String apiBaseUrl = 'http://10.0.2.2:8000',
  String supabaseUrl = 'https://project.supabase.co',
  String supabaseAnonKey = 'anon-key',
}) {
  return AppConfig(
    useMock: useMock,
    readSource: readSource,
    apiBaseUrl: apiBaseUrl,
    supabaseUrl: supabaseUrl,
    supabaseAnonKey: supabaseAnonKey,
  );
}

void main() {
  group('validate', () {
    test('accepts mock mode with nothing else configured', () {
      final config = _config(
        useMock: true,
        readSource: null,
        supabaseUrl: '',
        supabaseAnonKey: '',
      );
      expect(config.validate(), isNull);
    });

    test('accepts a complete real configuration', () {
      expect(_config().validate(), isNull);
    });

    test('requires Supabase when mocks are off', () {
      expect(_config(supabaseAnonKey: '').validate(), contains('SUPABASE'));
    });

    test('rejects an unknown READ_SOURCE', () {
      expect(_config(readSource: null).validate(), contains('READ_SOURCE'));
    });

    test('rejects an API_BASE_URL without a scheme', () {
      expect(
        _config(apiBaseUrl: 'localhost:8000').validate(),
        contains('API_BASE_URL'),
      );
    });
  });

  test('parseReadSource ignores case and whitespace', () {
    expect(AppConfig.parseReadSource('api'), ReadSource.api);
    expect(AppConfig.parseReadSource(' Supabase '), ReadSource.supabase);
    expect(AppConfig.parseReadSource('graphql'), isNull);
  });

  test('fromEnvironment defaults to mock mode on the emulator URL', () {
    final config = AppConfig.fromEnvironment();
    expect(config.useMock, isTrue);
    expect(config.apiBaseUrl, 'http://10.0.2.2:8000');
    expect(config.validate(), isNull);
  });
}
