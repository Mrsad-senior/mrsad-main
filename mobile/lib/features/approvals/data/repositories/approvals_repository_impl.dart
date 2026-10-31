import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/repositories/approvals_repository.dart';

class ApprovalsRepositoryImpl implements ApprovalsRepository {
  ApprovalsRepositoryImpl({required this._reads, required this._decisions});

  final ApprovalsReadDataSource _reads;
  final ApprovalDecisionDataSource _decisions;

  @override
  Stream<Either<Failure, List<Approval>>> watchPending() {
    return guardStream(
      _reads.watchPending().map(
        (models) => [for (final model in models) model.toEntity()],
      ),
    );
  }

  @override
  Future<Either<Failure, Unit>> refreshPending() {
    return guard(() async {
      await _reads.refreshPending();
      return unit;
    });
  }

  @override
  Future<Either<Failure, Approval>> getApproval(String id) {
    return guard(() async => (await _reads.getApproval(id)).toEntity());
  }

  @override
  Future<Either<Failure, Approval>> decide({
    required String id,
    required ReviewDecision decision,
    String? note,
  }) {
    return guard(() async {
      final request = DecisionRequestModel(decision: decision, note: note);
      return (await _decisions.submitDecision(id, request)).toEntity();
    });
  }
}
