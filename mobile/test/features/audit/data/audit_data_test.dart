import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/audit/data/datasources/audit_api_data_source.dart';
import 'package:mirsad/features/audit/data/datasources/audit_mock_data_source.dart';
import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';

import '../../../helpers/fake_http_adapter.dart';

/// `GET /api/stats/overview`, trimmed to the fields around the audit status.
Map<String, dynamic> _overview({bool? auditOk = true, int? firstBadSeq}) {
  return {
    'hours': 1.0,
    'total_calls': 2,
    'allowed': 1,
    'denied': 1,
    'approvals_pending': 0,
    'audit_ok': auditOk,
    'audit_head_seq': 5,
    'audit_first_bad_seq': ?firstBadSeq,
    'by_tool': <Object>[],
    'by_layer': <Object>[],
  };
}

void main() {
  group('AuditChainStatusModel', () {
    test('reads an intact chain', () {
      final status = AuditChainStatusModel.fromJson(_overview()).toEntity();
      expect(status, const AuditChainStatus.intact());
    });

    test('reads a broken chain without an entry, as the gateway sends it', () {
      final status = AuditChainStatusModel.fromJson(
        _overview(auditOk: false),
      ).toEntity();
      expect(status, const AuditChainStatus(valid: false));
    });

    test('reads the broken entry once the gateway sends it', () {
      final status = AuditChainStatusModel.fromJson(
        _overview(auditOk: false, firstBadSeq: 1287),
      ).toEntity();
      expect(status, const AuditChainStatus(valid: false, brokenAt: 1287));
    });

    test('ignores the broken entry when the chain is valid', () {
      final status = AuditChainStatusModel.fromJson(
        _overview(firstBadSeq: 3),
      ).toEntity();
      expect(status, const AuditChainStatus.intact());
    });
  });

  group('AuditApiDataSource', () {
    late FakeHttpAdapter adapter;

    setUp(() => adapter = FakeHttpAdapter());

    test('reads the status from GET /api/stats/overview', () async {
      adapter.on('GET', '/api/stats/overview', body: _overview(auditOk: false));

      final model = await AuditApiDataSource(fakeDio(adapter)).verify();

      expect(model.auditOk, isFalse);
      expect(adapter.requests.single.queryParameters, {'hours': 1});
    });

    test(
      'a status the gateway could not compute is a ServerException',
      () async {
        adapter.on(
          'GET',
          '/api/stats/overview',
          body: _overview(auditOk: null),
        );
        await expectLater(
          AuditApiDataSource(fakeDio(adapter)).verify(),
          throwsA(isA<ServerException>()),
        );
      },
    );

    test('a 500 is a ServerException', () async {
      adapter.on(
        'GET',
        '/api/stats/overview',
        status: 500,
        body: {'detail': 'Internal server error'},
      );
      await expectLater(
        AuditApiDataSource(fakeDio(adapter)).verify(),
        throwsA(isA<ServerException>()),
      );
    });
  });

  test('the mock reports an intact chain unless told otherwise', () async {
    const intact = AuditMockDataSource(latency: Duration.zero);
    const broken = AuditMockDataSource(brokenAt: 7, latency: Duration.zero);
    expect((await intact.verify()).toEntity().valid, isTrue);
    expect((await broken.verify()).toEntity().brokenAt, 7);
  });
}
