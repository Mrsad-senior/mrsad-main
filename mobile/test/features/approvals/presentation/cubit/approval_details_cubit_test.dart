import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/presentation/cubit/approval_details_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockGetApproval getApproval;
  late MockDecideApproval decide;
  final held = transferApproval();
  final rejected = transferApproval(status: ApprovalStatus.rejected);
  final expired = transferApproval(status: ApprovalStatus.expired);

  setUpAll(() => registerFallbackValue(ReviewDecision.approve));

  setUp(() {
    getApproval = MockGetApproval();
    decide = MockDecideApproval();
  });

  ApprovalDetailsCubit build() =>
      ApprovalDetailsCubit(getApproval: getApproval, decide: decide);

  final readyState = ApprovalDetailsState(
    status: ApprovalDetailsStatus.ready,
    approval: held,
  );

  group('load', () {
    blocTest<ApprovalDetailsCubit, ApprovalDetailsState>(
      'shows the approval',
      setUp: () => when(
        () => getApproval('apr_7f3c2a'),
      ).thenAnswer((_) async => Right(held)),
      build: build,
      act: (cubit) => cubit.load('apr_7f3c2a'),
      expect: () => [const ApprovalDetailsState(), readyState],
    );

    blocTest<ApprovalDetailsCubit, ApprovalDetailsState>(
      'shows why it could not load',
      setUp: () => when(
        () => getApproval('apr_7f3c2a'),
      ).thenAnswer((_) async => const Left(NetworkFailure())),
      build: build,
      act: (cubit) => cubit.load('apr_7f3c2a'),
      expect: () => const [
        ApprovalDetailsState(),
        ApprovalDetailsState(
          status: ApprovalDetailsStatus.failure,
          loadFailure: NetworkFailure(),
        ),
      ],
    );
  });

  group('decide', () {
    void whenDecided(Either<Failure, Approval> result) {
      when(
        () => decide(
          id: any(named: 'id'),
          decision: any(named: 'decision'),
          note: any(named: 'note'),
        ),
      ).thenAnswer((_) async => result);
    }

    blocTest<ApprovalDetailsCubit, ApprovalDetailsState>(
      'submits, then shows the new status',
      setUp: () => whenDecided(Right(rejected)),
      build: build,
      seed: () => readyState,
      act: (cubit) => cubit.decide(ReviewDecision.reject, note: 'Unknown IBAN'),
      expect: () => [
        ApprovalDetailsState(
          status: ApprovalDetailsStatus.ready,
          approval: held,
          submission: DecisionSubmission.submitting,
          decision: ReviewDecision.reject,
        ),
        ApprovalDetailsState(
          status: ApprovalDetailsStatus.ready,
          approval: rejected,
          submission: DecisionSubmission.succeeded,
          decision: ReviewDecision.reject,
        ),
      ],
      verify: (_) => verify(
        () => decide(
          id: 'apr_7f3c2a',
          decision: ReviewDecision.reject,
          note: 'Unknown IBAN',
        ),
      ).called(1),
    );

    blocTest<ApprovalDetailsCubit, ApprovalDetailsState>(
      'keeps the approval and reports a failed submission',
      setUp: () => whenDecided(const Left(NetworkFailure())),
      build: build,
      seed: () => readyState,
      act: (cubit) => cubit.decide(ReviewDecision.approve),
      expect: () => [
        ApprovalDetailsState(
          status: ApprovalDetailsStatus.ready,
          approval: held,
          submission: DecisionSubmission.submitting,
          decision: ReviewDecision.approve,
        ),
        ApprovalDetailsState(
          status: ApprovalDetailsStatus.ready,
          approval: held,
          submission: DecisionSubmission.failed,
          decision: ReviewDecision.approve,
          submitFailure: const NetworkFailure(),
        ),
      ],
    );

    blocTest<ApprovalDetailsCubit, ApprovalDetailsState>(
      'reloads after a conflict to show the real status',
      setUp: () {
        whenDecided(const Left(ConflictFailure()));
        when(
          () => getApproval('apr_7f3c2a'),
        ).thenAnswer((_) async => Right(expired));
      },
      build: build,
      seed: () => readyState,
      act: (cubit) => cubit.decide(ReviewDecision.approve),
      skip: 2,
      expect: () => [
        ApprovalDetailsState(
          status: ApprovalDetailsStatus.ready,
          approval: expired,
          submission: DecisionSubmission.failed,
          decision: ReviewDecision.approve,
          submitFailure: const ConflictFailure(),
        ),
      ],
    );

    blocTest<ApprovalDetailsCubit, ApprovalDetailsState>(
      'does nothing before the approval has loaded',
      build: build,
      act: (cubit) => cubit.decide(ReviewDecision.approve),
      expect: () => const <ApprovalDetailsState>[],
      verify: (_) => verifyNever(
        () => decide(
          id: any(named: 'id'),
          decision: any(named: 'decision'),
          note: any(named: 'note'),
        ),
      ),
    );
  });
}
