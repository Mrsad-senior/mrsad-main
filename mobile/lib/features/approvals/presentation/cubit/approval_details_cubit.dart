import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/usecases/decide_approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/get_approval.dart';

part 'approval_details_state.dart';

class ApprovalDetailsCubit extends Cubit<ApprovalDetailsState> {
  ApprovalDetailsCubit({required this._getApproval, required this._decide})
    : super(const ApprovalDetailsState());

  final GetApproval _getApproval;
  final DecideApproval _decide;
  String? _id;

  Future<void> load(String id) async {
    _id = id;
    emit(const ApprovalDetailsState());
    final result = await _getApproval(id);
    emit(
      result.match(
        (failure) => ApprovalDetailsState(
          status: ApprovalDetailsStatus.failure,
          loadFailure: failure,
        ),
        (approval) => ApprovalDetailsState(
          status: ApprovalDetailsStatus.ready,
          approval: approval,
        ),
      ),
    );
  }

  Future<void> retry() async {
    final id = _id;
    if (id != null) await load(id);
  }

  Future<void> decide(ReviewDecision decision, {String? note}) async {
    final approval = state.approval;
    if (approval == null || state.isSubmitting) return;

    emit(_ready(approval, DecisionSubmission.submitting, decision));
    final result = await _decide(
      id: approval.id,
      decision: decision,
      note: note,
    );
    await result.match(
      (failure) async {
        emit(_ready(approval, DecisionSubmission.failed, decision, failure));
        // Someone else decided, or it expired: show its real status.
        if (failure is ConflictFailure) await _reload(approval.id, failure);
      },
      (updated) async =>
          emit(_ready(updated, DecisionSubmission.succeeded, decision)),
    );
  }

  Future<void> _reload(String id, Failure failure) async {
    final result = await _getApproval(id);
    result.match(
      (_) {},
      (fresh) => emit(
        _ready(fresh, DecisionSubmission.failed, state.decision, failure),
      ),
    );
  }

  ApprovalDetailsState _ready(
    Approval approval,
    DecisionSubmission submission,
    ReviewDecision? decision, [
    Failure? submitFailure,
  ]) {
    return ApprovalDetailsState(
      status: ApprovalDetailsStatus.ready,
      approval: approval,
      submission: submission,
      decision: decision,
      submitFailure: submitFailure,
    );
  }
}
