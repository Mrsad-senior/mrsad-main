import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/presentation/cubit/pending_approvals_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockWatchPendingApprovals watchPending;
  late MockRefreshPendingApprovals refreshPending;
  late StreamController<Either<Failure, List<Approval>>> results;
  final approval = transferApproval();

  setUp(() {
    watchPending = MockWatchPendingApprovals();
    refreshPending = MockRefreshPendingApprovals();
    results = StreamController.broadcast();
    when(() => watchPending()).thenAnswer((_) => results.stream);
  });

  tearDown(() => results.close());

  PendingApprovalsCubit build() => PendingApprovalsCubit(
    watchPending: watchPending,
    refreshPending: refreshPending,
  );

  final ready = PendingApprovalsState(
    status: PendingApprovalsStatus.ready,
    approvals: [approval],
  );

  test('starts loading', () {
    expect(build().state.status, PendingApprovalsStatus.loading);
  });

  blocTest<PendingApprovalsCubit, PendingApprovalsState>(
    'shows the list when it arrives',
    build: build,
    act: (cubit) {
      cubit.start();
      results.add(Right([approval]));
    },
    expect: () => [ready],
  );

  blocTest<PendingApprovalsCubit, PendingApprovalsState>(
    'shows an error when the first load fails',
    build: build,
    act: (cubit) {
      cubit.start();
      results.add(const Left(NetworkFailure()));
    },
    expect: () => const [
      PendingApprovalsState(
        status: PendingApprovalsStatus.failure,
        failure: NetworkFailure(),
      ),
    ],
  );

  blocTest<PendingApprovalsCubit, PendingApprovalsState>(
    'keeps the list when a later update fails',
    build: build,
    act: (cubit) {
      cubit.start();
      results
        ..add(Right([approval]))
        ..add(const Left(NetworkFailure()));
    },
    expect: () => [
      ready,
      PendingApprovalsState(
        status: PendingApprovalsStatus.ready,
        approvals: [approval],
        failure: const NetworkFailure(),
      ),
    ],
  );

  blocTest<PendingApprovalsCubit, PendingApprovalsState>(
    'reports a failed refresh without dropping the list',
    setUp: () => when(
      () => refreshPending(),
    ).thenAnswer((_) async => const Left(ServerFailure())),
    build: build,
    seed: () => ready,
    act: (cubit) => cubit.refresh(),
    expect: () => [
      PendingApprovalsState(
        status: PendingApprovalsStatus.ready,
        approvals: [approval],
        failure: const ServerFailure(),
      ),
    ],
  );

  blocTest<PendingApprovalsCubit, PendingApprovalsState>(
    'retry starts a fresh subscription',
    build: build,
    act: (cubit) async {
      cubit.start();
      results.add(const Left(NetworkFailure()));
      await Future<void>.delayed(Duration.zero);
      await cubit.retry();
      results.add(Right([approval]));
    },
    expect: () => [
      const PendingApprovalsState(
        status: PendingApprovalsStatus.failure,
        failure: NetworkFailure(),
      ),
      const PendingApprovalsState(),
      ready,
    ],
    verify: (_) => verify(() => watchPending()).called(2),
  );
}
