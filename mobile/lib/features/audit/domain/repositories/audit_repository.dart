import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';

abstract interface class AuditRepository {
  /// Asks the gateway to walk the audit hash chain.
  Future<Either<Failure, AuditChainStatus>> verify();
}
