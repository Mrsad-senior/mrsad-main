import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';

/// Re-fetches the pending approvals, e.g. on pull-to-refresh.
class RefreshPendingApprovals {
  const RefreshPendingApprovals(this._repository);

  final ApprovalsRepository _repository;

  Future<Either<Failure, Unit>> call() => _repository.refreshPending();
}
