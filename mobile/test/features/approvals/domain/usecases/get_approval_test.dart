import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/get_approval.dart';
import 'package:mocktail/mocktail.dart';

import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockApprovalsRepository repository;

  setUp(() => repository = MockApprovalsRepository());

  test('returns the approval with that id', () async {
    final approval = transferApproval();
    when(
      () => repository.getApproval('apr_7f3c2a'),
    ).thenAnswer((_) async => Right(approval));

    expect(
      await GetApproval(repository)('apr_7f3c2a'),
      Right<Failure, Approval>(approval),
    );
  });

  test('returns NotFoundFailure for an unknown id', () async {
    when(
      () => repository.getApproval('missing'),
    ).thenAnswer((_) async => const Left(NotFoundFailure()));

    expect(
      await GetApproval(repository)('missing'),
      const Left<Failure, Approval>(NotFoundFailure()),
    );
  });
}
