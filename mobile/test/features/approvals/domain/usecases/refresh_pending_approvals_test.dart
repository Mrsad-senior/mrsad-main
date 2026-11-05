import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/usecases/refresh_pending_approvals.dart';
import 'package:mocktail/mocktail.dart';

import '../../approvals_mocks.dart';

void main() {
  late MockApprovalsRepository repository;

  setUp(() => repository = MockApprovalsRepository());

  test('asks the repository to refresh', () async {
    when(
      () => repository.refreshPending(),
    ).thenAnswer((_) async => const Right(unit));

    final result = await RefreshPendingApprovals(repository)();

    expect(result, const Right<Failure, Unit>(unit));
    verify(() => repository.refreshPending()).called(1);
  });

  test('returns the repository failure', () async {
    when(
      () => repository.refreshPending(),
    ).thenAnswer((_) async => const Left(NetworkFailure()));

    expect(
      await RefreshPendingApprovals(repository)(),
      const Left<Failure, Unit>(NetworkFailure()),
    );
  });
}
