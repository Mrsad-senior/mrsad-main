import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/config/app_config.dart';

void main() {
  group('validate', () {
    test('accepts mock mode with nothing else configured', () {
      const config = AppConfig(useMock: true, apiBaseUrl: '');
      expect(config.validate(), isNull);
    });

    test('accepts the gateway on an absolute URL', () {
      const config = AppConfig(
        useMock: false,
        apiBaseUrl: 'https://api.mirsad-app.com',
      );
      expect(config.validate(), isNull);
    });

    test('rejects an API_BASE_URL without a scheme', () {
      const config = AppConfig(useMock: false, apiBaseUrl: 'localhost:8700');
      expect(config.validate(), contains('API_BASE_URL'));
    });
  });

  test('fromEnvironment defaults to mock mode on the emulator URL', () {
    final config = AppConfig.fromEnvironment();
    expect(config.useMock, isTrue);
    expect(config.apiBaseUrl, 'http://10.0.2.2:8700');
    expect(config.validate(), isNull);
  });
}
