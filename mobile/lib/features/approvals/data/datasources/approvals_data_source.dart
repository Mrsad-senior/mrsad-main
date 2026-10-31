import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';

/// Reads held approvals. Implemented by the mock, API and Supabase sources.
///
/// Methods throw `AppException`s on failure.
abstract interface class ApprovalsReadDataSource {
  /// Emits the held approvals now and whenever they change. Errors arrive as
  /// stream errors and do not end the stream.
  Stream<List<ApprovalModel>> watchPending();

  /// Fetches the held approvals again and pushes them to [watchPending].
  Future<void> refreshPending();

  Future<ApprovalModel> getApproval(String id);
}

/// Sends reviewer decisions. Only the gateway (or its mock) can resume or
/// cancel the agent's action, so Supabase does not implement this.
abstract interface class ApprovalDecisionDataSource {
  /// Returns the approval with its new status. Sources that also implement
  /// [ApprovalsReadDataSource] update their pending list themselves.
  Future<ApprovalModel> submitDecision(String id, DecisionRequestModel request);
}
