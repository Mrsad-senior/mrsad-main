import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';

abstract interface class ApprovalsRepository {
  /// The held approvals, re-emitted whenever the set changes. A failed
  /// update arrives as a [Left] and the stream stays open.
  Stream<Either<Failure, List<Approval>>> watchPending();

  /// Fetches the pending list again now; the result arrives on
  /// [watchPending].
  Future<Either<Failure, Unit>> refreshPending();

  Future<Either<Failure, Approval>> getApproval(String id);

  /// Sends the reviewer's decision to the gateway and returns the updated
  /// approval.
  Future<Either<Failure, Approval>> decide({
    required String id,
    required ReviewDecision decision,
    String? note,
  });
}
