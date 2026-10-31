import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/audit/data/datasources/audit_data_source.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';
import 'package:mirsad/features/audit/domain/repositories/audit_repository.dart';

class AuditRepositoryImpl implements AuditRepository {
  const AuditRepositoryImpl(this._source);

  final AuditDataSource _source;

  @override
  Future<Either<Failure, AuditChainStatus>> verify() {
    return guard(() async => (await _source.verify()).toEntity());
  }
}
