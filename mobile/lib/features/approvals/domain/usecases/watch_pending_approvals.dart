import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';

/// The pending approvals, most urgent (soonest to expire) first.
class WatchPendingApprovals {
  const WatchPendingApprovals(this._repository);

  final ApprovalsRepository _repository;

  Stream<Either<Failure, List<Approval>>> call() {
    return _repository.watchPending().map(
      (result) => result.map(
        (approvals) =>
            [...approvals]..sort((a, b) => a.expiresAt.compareTo(b.expiresAt)),
      ),
    );
  }
}
