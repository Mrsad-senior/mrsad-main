import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/usecases/decide_approval.dart';
import 'package:mocktail/mocktail.dart';

import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockApprovalsRepository repository;
  late DecideApproval decide;

  setUp(() {
    repository = MockApprovalsRepository();
    decide = DecideApproval(repository);
    when(
      () => repository.decide(
        id: any(named: 'id'),
        decision: any(named: 'decision'),
        note: any(named: 'note'),
      ),
    ).thenAnswer(
      (_) async => Right(transferApproval(status: ApprovalStatus.rejected)),
    );
  });

  setUpAll(() => registerFallbackValue(ReviewDecision.approve));

  String? sentNote() {
    return verify(
          () => repository.decide(
            id: 'apr_7f3c2a',
            decision: ReviewDecision.reject,
            note: captureAny(named: 'note'),
          ),
        ).captured.single
        as String?;
  }

  test('sends the decision with a trimmed note', () async {
    await decide(
      id: 'apr_7f3c2a',
      decision: ReviewDecision.reject,
      note: '  IBAN not on file  ',
    );
    expect(sentNote(), 'IBAN not on file');
  });

  test('sends a blank note as no note', () async {
    await decide(id: 'apr_7f3c2a', decision: ReviewDecision.reject, note: '  ');
    expect(sentNote(), isNull);
  });

  test('cuts a long note to the gateway limit', () async {
    await decide(
      id: 'apr_7f3c2a',
      decision: ReviewDecision.reject,
      note: 'x' * 600,
    );
    expect(sentNote(), hasLength(DecideApproval.maxNoteLength));
  });

  test('returns the updated approval', () async {
    final result = await decide(
      id: 'apr_7f3c2a',
      decision: ReviewDecision.reject,
    );
    expect(result.isRight(), isTrue);
  });
}
