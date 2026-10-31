import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';
import 'package:mirsad/features/audit/data/repositories/audit_repository_impl.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';
import 'package:mocktail/mocktail.dart';

import '../../audit_mocks.dart';

void main() {
  late MockAuditDataSource source;
  late AuditRepositoryImpl repository;

  setUp(() {
    source = MockAuditDataSource();
    repository = AuditRepositoryImpl(source);
  });

  test('maps the model to an entity', () async {
    when(() => source.verify()).thenAnswer(
      (_) async => const AuditChainStatusModel(valid: false, brokenAt: 9),
    );

    expect(
      await repository.verify(),
      const Right<Failure, AuditChainStatus>(
        AuditChainStatus(valid: false, brokenAt: 9),
      ),
    );
  });

  test('maps exceptions to failures', () async {
    when(() => source.verify()).thenThrow(const UnauthorizedException());

    expect(
      await repository.verify(),
      const Left<Failure, AuditChainStatus>(UnauthorizedFailure()),
    );
  });
}
