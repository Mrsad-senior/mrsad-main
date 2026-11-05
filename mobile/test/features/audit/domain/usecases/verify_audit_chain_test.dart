import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';
import 'package:mirsad/features/audit/domain/usecases/verify_audit_chain.dart';
import 'package:mocktail/mocktail.dart';

import '../../audit_mocks.dart';

void main() {
  late MockAuditRepository repository;

  setUp(() => repository = MockAuditRepository());

  test('returns the chain status from the repository', () async {
    const broken = AuditChainStatus(valid: false, brokenAt: 1287);
    when(
      () => repository.verify(),
    ).thenAnswer((_) async => const Right(broken));

    expect(
      await VerifyAuditChain(repository)(),
      const Right<Failure, AuditChainStatus>(broken),
    );
  });

  test('returns the repository failure', () async {
    when(
      () => repository.verify(),
    ).thenAnswer((_) async => const Left(NetworkFailure()));

    expect(
      await VerifyAuditChain(repository)(),
      const Left<Failure, AuditChainStatus>(NetworkFailure()),
    );
  });
}
