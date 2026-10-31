import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';
import 'package:mirsad/features/audit/domain/repositories/audit_repository.dart';

class VerifyAuditChain {
  const VerifyAuditChain(this._repository);

  final AuditRepository _repository;

  Future<Either<Failure, AuditChainStatus>> call() => _repository.verify();
}
