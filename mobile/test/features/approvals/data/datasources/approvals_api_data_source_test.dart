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

  test('GET /approvals/pending feeds watchPending', () async {
    adapter.on('GET', '/approvals/pending', body: [approvalJson()]);

    final pending = await source.watchPending().first;

    expect(pending.single.id, 'apr_7f3c2a');
  });

  test('refreshPending pushes a new list to watchers', () async {
    adapter.on('GET', '/approvals/pending', body: [approvalJson()]);
    final counts = <int>[];
    final firstFetch = Completer<void>();
    final subscription = source.watchPending().listen((list) {
      counts.add(list.length);
      if (!firstFetch.isCompleted) firstFetch.complete();
    });
    await firstFetch.future;

    adapter.on('GET', '/approvals/pending', body: <Object>[]);
    await source.refreshPending();
    await Future<void>.delayed(Duration.zero);

    expect(counts, [1, 0]);
    await subscription.cancel();
  });

  test('GET /approvals/{id} returns one approval', () async {
    adapter.on('GET', '/approvals/apr_7f3c2a', body: approvalJson());
    expect((await source.getApproval('apr_7f3c2a')).tool, 'transfer_funds');
  });

  test('POST /approvals/{id} sends the decision and note', () async {
    adapter
      ..on(
        'POST',
        '/approvals/apr_7f3c2a',
        body: approvalJson(status: 'rejected'),
      )
      ..on('GET', '/approvals/pending', body: <Object>[]);

    final updated = await source.submitDecision('apr_7f3c2a', _reject);

    expect(updated.status, ApprovalStatus.rejected);
    final post = adapter.requests.firstWhere((r) => r.method == 'POST');
    expect(post.data, {'decision': 'reject', 'note': 'Unknown IBAN'});
  });

  test('a 409 from the gateway is a ConflictException', () async {
    adapter.on(
      'POST',
      '/approvals/apr_7f3c2a',
      status: 409,
      body: {'detail': 'Approval is no longer held'},
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
