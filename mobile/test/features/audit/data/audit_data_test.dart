import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/audit/data/datasources/audit_api_data_source.dart';
import 'package:mirsad/features/audit/data/datasources/audit_mock_data_source.dart';
import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';

import '../../../helpers/fake_http_adapter.dart';

void main() {
  group('AuditChainStatusModel', () {
    test('parses a broken chain', () {
      final status = AuditChainStatusModel.fromJson(const {
        'valid': false,
        'broken_at': 1287,
      }).toEntity();
      expect(status, const AuditChainStatus(valid: false, brokenAt: 1287));
    });

    test('ignores broken_at when the chain is valid', () {
      final status = AuditChainStatusModel.fromJson(const {
        'valid': true,
        'broken_at': 3,
      }).toEntity();
      expect(status, const AuditChainStatus.intact());
    });
  });

  group('AuditApiDataSource', () {
    late FakeHttpAdapter adapter;

    setUp(() => adapter = FakeHttpAdapter());

    test('GET /audit/verify returns the chain status', () async {
      adapter.on(
        'GET',
        '/audit/verify',
        body: {'valid': false, 'broken_at': 42},
      );
      final model = await AuditApiDataSource(fakeDio(adapter)).verify();
      expect(model.brokenAt, 42);
    });

    test('a 500 is a ServerException', () async {
      adapter.on('GET', '/audit/verify', status: 500, body: {'detail': 'x'});
      await expectLater(
        AuditApiDataSource(fakeDio(adapter)).verify(),
        throwsA(isA<ServerException>()),
      );
    });
  });

  test('the mock reports an intact chain unless told otherwise', () async {
    const intact = AuditMockDataSource(latency: Duration.zero);
    const broken = AuditMockDataSource(brokenAt: 7, latency: Duration.zero);
    expect((await intact.verify()).valid, isTrue);
    expect((await broken.verify()).brokenAt, 7);
  });
}
