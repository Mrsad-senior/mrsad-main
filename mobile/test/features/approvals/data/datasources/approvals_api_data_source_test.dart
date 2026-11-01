import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_api_data_source.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';

import '../../../../helpers/fake_http_adapter.dart';
import '../../approval_fixtures.dart';

const _reject = DecisionRequestModel(
  decision: ReviewDecision.reject,
  note: 'Unknown IBAN',
);

void main() {
  late FakeHttpAdapter adapter;
  late ApprovalsApiDataSource source;

  setUp(() {
    adapter = FakeHttpAdapter();
    source = ApprovalsApiDataSource(
      fakeDio(adapter),
      pollInterval: const Duration(hours: 1),
    );
  });

  tearDown(() => source.dispose());

  test('GET /api/approvals?status=pending feeds watchPending', () async {
    adapter.on('GET', '/api/approvals', body: [approvalJson()]);

    final pending = await source.watchPending().first;

    expect(pending.single.id, 'apr_7f3c2a');
    expect(adapter.requests.single.queryParameters, {
      'status': 'pending',
      'limit': 100,
    });
  });

  test('refreshPending pushes a new list to watchers', () async {
    adapter.on('GET', '/api/approvals', body: [approvalJson()]);
    final counts = <int>[];
    final firstFetch = Completer<void>();
    final subscription = source.watchPending().listen((list) {
      counts.add(list.length);
      if (!firstFetch.isCompleted) firstFetch.complete();
    });
    await firstFetch.future;

    adapter.on('GET', '/api/approvals', body: <Object>[]);
    await source.refreshPending();
    await Future<void>.delayed(Duration.zero);

    expect(counts, [1, 0]);
    await subscription.cancel();
  });

  test('GET /api/approvals/{id} returns one approval', () async {
    adapter.on('GET', '/api/approvals/apr_7f3c2a', body: approvalJson());
    expect((await source.getApproval('apr_7f3c2a')).tool, 'transfer_funds');
  });

  test('POST /api/approvals/{id}/decision sends the decision', () async {
    adapter
      ..on(
        'POST',
        '/api/approvals/apr_7f3c2a/decision',
        body: approvalJson(status: 'denied'),
      )
      ..on('GET', '/api/approvals', body: <Object>[]);

    final updated = await source.submitDecision('apr_7f3c2a', _reject);

    expect(updated.status, ApprovalStatus.rejected);
    final post = adapter.requests.firstWhere((r) => r.method == 'POST');
    expect(post.data, {'approve': false, 'note': 'Unknown IBAN'});
  });

  test('a 409 from the gateway is a ConflictException', () async {
    adapter.on(
      'POST',
      '/api/approvals/apr_7f3c2a/decision',
      status: 409,
      body: {'detail': 'approval apr_7f3c2a is already denied'},
    );
    await expectLater(
      source.submitDecision('apr_7f3c2a', _reject),
      throwsA(isA<ConflictException>()),
    );
  });

  test('a 404 from the gateway is a NotFoundException', () async {
    await expectLater(
      source.getApproval('missing'),
      throwsA(isA<NotFoundException>()),
    );
  });
}
