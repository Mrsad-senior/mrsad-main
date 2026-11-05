import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';

class GetApproval {
  const GetApproval(this._repository);

  final ApprovalsRepository _repository;

  Future<Either<Failure, Approval>> call(String id) =>
      _repository.getApproval(id);
}
