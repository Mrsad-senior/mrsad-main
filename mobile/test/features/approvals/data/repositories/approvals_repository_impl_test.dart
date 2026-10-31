import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/data/repositories/approvals_repository_impl.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/either.dart';
import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockApprovalsReadDataSource reads;
  late MockApprovalDecisionDataSource decisions;
  late ApprovalsRepositoryImpl repository;

  setUpAll(() {
    registerFallbackValue(
      const DecisionRequestModel(decision: ReviewDecision.approve),
    );
  });

  setUp(() {
    reads = MockApprovalsReadDataSource();
    decisions = MockApprovalDecisionDataSource();
    repository = ApprovalsRepositoryImpl(reads: reads, decisions: decisions);
  });

  group('watchPending', () {
    test('maps models to entities', () async {
      when(() => reads.watchPending()).thenAnswer(
        (_) => Stream.value([ApprovalModel.fromJson(approvalJson())]),
      );

      final result = await repository.watchPending().first;

      expect(rightOf(result).single.tool, 'transfer_funds');
    });

    test('turns a stream error into a Left', () async {
      when(
        () => reads.watchPending(),
      ).thenAnswer((_) => Stream.error(const NetworkException()));

      expect(
        await repository.watchPending().first,
        const Left<Failure, List<Approval>>(NetworkFailure()),
      );
    });
  });

  test('refreshPending returns a failure instead of throwing', () async {
    when(
      () => reads.refreshPending(),
    ).thenThrow(const ServerException(statusCode: 500));

    expect(
      await repository.refreshPending(),
      const Left<Failure, Unit>(ServerFailure(statusCode: 500)),
    );
  });

  test('getApproval maps NotFoundException', () async {
    when(
      () => reads.getApproval('missing'),
    ).thenThrow(const NotFoundException());

    expect(
      await repository.getApproval('missing'),
      const Left<Failure, Approval>(NotFoundFailure()),
    );
  });

  group('decide', () {
    test('sends the decision and note to the gateway source', () async {
      when(() => decisions.submitDecision(any(), any())).thenAnswer(
        (_) async => ApprovalModel.fromJson(approvalJson(status: 'rejected')),
      );

      final result = await repository.decide(
        id: 'apr_7f3c2a',
        decision: ReviewDecision.reject,
        note: 'Unknown IBAN',
      );

      expect(rightOf(result).status, ApprovalStatus.rejected);
      final request =
          verify(
                () => decisions.submitDecision('apr_7f3c2a', captureAny()),
              ).captured.single
              as DecisionRequestModel;
      expect(request.decision, ReviewDecision.reject);
      expect(request.note, 'Unknown IBAN');
    });

    test('maps ConflictException to ConflictFailure', () async {
      when(
        () => decisions.submitDecision(any(), any()),
      ).thenThrow(const ConflictException());

      final result = await repository.decide(
        id: 'apr_7f3c2a',
        decision: ReviewDecision.approve,
      );

      expect(result, const Left<Failure, Approval>(ConflictFailure()));
    });
  });
}
