import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_mock_data_source.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';

import '../../../../helpers/fake_clock.dart';

const _transferId = 'apr_7f3c2a';
const _reject = DecisionRequestModel(decision: ReviewDecision.reject);

void main() {
  late FakeClock clock;
  late ApprovalsMockDataSource source;

  setUp(() {
    clock = FakeClock(testNow);
    source = ApprovalsMockDataSource(clock: clock, latency: Duration.zero);
  });

  tearDown(() => source.dispose());

  test('starts with the finance demo approvals held', () async {
    final pending = await source.watchPending().first;
    expect(pending.map((a) => a.tool), ['transfer_funds', 'send_email']);
    expect(pending.first.arguments['amount'], 50000);
  });

  test('a decision removes the approval from the pending list', () async {
    final counts = source.watchPending().map((list) => list.length);
    final expectation = expectLater(counts, emitsInOrder([2, 1]));
    await Future<void>.delayed(Duration.zero);

    final decided = await source.submitDecision(_transferId, _reject);

    expect(decided.status, ApprovalStatus.rejected);
    await expectation;
  });

  test('deciding twice is a conflict', () async {
    await source.submitDecision(_transferId, _reject);
    await expectLater(
      source.submitDecision(_transferId, _reject),
      throwsA(isA<ConflictException>()),
    );
  });

  test('held approvals expire after five minutes', () async {
    clock.advance(const Duration(minutes: 5));

    expect(await source.watchPending().first, isEmpty);
    expect(
      (await source.getApproval(_transferId)).status,
      ApprovalStatus.expired,
    );
    await expectLater(
      source.submitDecision(_transferId, _reject),
      throwsA(isA<ConflictException>()),
    );
  });

  test('refreshing an empty list brings the demo back', () async {
    clock.advance(const Duration(minutes: 5));
    await source.refreshPending();
    expect(await source.watchPending().first, hasLength(2));
  });

  test('an unknown id is not found', () async {
    await expectLater(
      source.getApproval('missing'),
      throwsA(isA<NotFoundException>()),
    );
  });
}
