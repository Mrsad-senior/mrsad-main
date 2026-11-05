import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/watch_pending_approvals.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/either.dart';
import '../../../../helpers/fake_clock.dart';
import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockApprovalsRepository repository;
  late WatchPendingApprovals watchPending;

  setUp(() {
    repository = MockApprovalsRepository();
    watchPending = WatchPendingApprovals(repository);
  });

  test('puts the approval that expires first at the top', () async {
    final later = transferApproval(
      id: 'later',
      expiresAt: testNow.add(const Duration(minutes: 4)),
    );
    final sooner = transferApproval(
      id: 'sooner',
      expiresAt: testNow.add(const Duration(minutes: 1)),
    );
    when(
      () => repository.watchPending(),
    ).thenAnswer((_) => Stream.value(Right([later, sooner])));

    final result = await watchPending().first;

    expect(rightOf(result).map((a) => a.id), ['sooner', 'later']);
  });

  test('passes failures through', () async {
    const failure = Left<Failure, List<Approval>>(NetworkFailure());
    when(
      () => repository.watchPending(),
    ).thenAnswer((_) => Stream.value(failure));

    expect(await watchPending().first, failure);
  });
}
