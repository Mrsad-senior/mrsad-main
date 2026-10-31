import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';
import 'package:mirsad/features/audit/presentation/cubit/audit_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../../audit_mocks.dart';

void main() {
  late MockVerifyAuditChain verifyAuditChain;
  const broken = AuditChainStatus(valid: false, brokenAt: 1287);
  const intactState = AuditState(
    status: AuditStatus.ready,
    result: AuditChainStatus.intact(),
  );

  setUp(() => verifyAuditChain = MockVerifyAuditChain());

  AuditCubit build() => AuditCubit(verifyAuditChain: verifyAuditChain);

  blocTest<AuditCubit, AuditState>(
    'shows the result of the first check',
    setUp: () => when(
      () => verifyAuditChain(),
    ).thenAnswer((_) async => const Right(broken)),
    build: build,
    act: (cubit) => cubit.verify(),
    expect: () => const [
      AuditState(),
      AuditState(status: AuditStatus.ready, result: broken),
    ],
  );

  blocTest<AuditCubit, AuditState>(
    'shows an error when the first check fails',
    setUp: () => when(
      () => verifyAuditChain(),
    ).thenAnswer((_) async => const Left(NetworkFailure())),
    build: build,
    act: (cubit) => cubit.verify(),
    expect: () => const [
      AuditState(),
      AuditState(status: AuditStatus.failure, failure: NetworkFailure()),
    ],
  );

  blocTest<AuditCubit, AuditState>(
    'keeps the last result on screen while checking again',
    setUp: () => when(
      () => verifyAuditChain(),
    ).thenAnswer((_) async => const Right(broken)),
    build: build,
    seed: () => intactState,
    act: (cubit) => cubit.verify(),
    expect: () => const [
      AuditState(
        status: AuditStatus.ready,
        result: AuditChainStatus.intact(),
        verifying: true,
      ),
      AuditState(status: AuditStatus.ready, result: broken),
    ],
  );

  blocTest<AuditCubit, AuditState>(
    'keeps the last result when a re-check fails',
    setUp: () => when(
      () => verifyAuditChain(),
    ).thenAnswer((_) async => const Left(ServerFailure())),
    build: build,
    seed: () => intactState,
    act: (cubit) => cubit.verify(),
    skip: 1,
    expect: () => const [
      AuditState(
        status: AuditStatus.ready,
        result: AuditChainStatus.intact(),
        failure: ServerFailure(),
      ),
    ],
  );
}
