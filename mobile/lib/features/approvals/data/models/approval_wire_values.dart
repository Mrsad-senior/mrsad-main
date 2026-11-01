import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

// How the gateway's values (docs/api.md, src/mirsad/models.py) map onto the
// domain enums. Kept here so the domain enums stay free of JSON concerns.

/// The gateway's name for a held approval.
const String pendingStatus = 'pending';

/// A reason whose `action` is this did not object to the call.
const String allowAction = 'allow';

const Map<String, ApprovalStatus> _statuses = {
  pendingStatus: ApprovalStatus.held,
  'approved': ApprovalStatus.approved,
  'denied': ApprovalStatus.rejected,
  'expired': ApprovalStatus.expired,
  // Withdrawn by the gateway, e.g. because the agent's session ended. Like an
  // expired approval, nobody can decide it any more.
  'cancelled': ApprovalStatus.expired,
};

ApprovalStatus approvalStatusFromJson(String value) {
  return _statuses[value] ??
      (throw DataFormatException('Unknown status "$value"'));
}

/// The gateway reports its task-intent checks under the `system` layer, so
/// the code says which check fired (src/mirsad/security/monitor.py).
const Map<String, ReasonLayer> _systemCodes = {
  'TASK_INTENT_MISMATCH': ReasonLayer.intent,
  'UNBOUND_TASK': ReasonLayer.intent,
  'SEMANTIC_TASK_MISMATCH': ReasonLayer.llmJudge,
  'NEW_BENEFICIARY': ReasonLayer.policy,
  'HEALTH_DATA_EXTERNAL': ReasonLayer.policy,
  'SENSITIVE_OUTBOUND': ReasonLayer.policy,
};

/// Unknown layers and codes become [ReasonLayer.other], so a new gateway
/// check does not break the app.
ReasonLayer reasonLayerFromWire(String layer, String code) {
  return switch (layer) {
    'policy' || 'ratelimit' || 'approval' => ReasonLayer.policy,
    'taint' => ReasonLayer.taint,
    'detector' => ReasonLayer.keywords,
    'system' => _systemCodes[code] ?? ReasonLayer.other,
    _ => ReasonLayer.other,
  };
}

/// Taint codes meaning that untrusted content (an email, a document, a web
/// page) reached the call. `TAINT_CONFIDENTIAL_TO_EXTERNAL` is about
/// confidential data leaving, not untrusted input, so it is not listed.
const Set<String> untrustedTaintCodes = {
  'TAINT_UNTRUSTED_DESTINATION',
  'TAINT_UNTRUSTED_TO_EXTERNAL',
  'TAINT_AFTER_INJECTION',
};

/// Approval records have no sector. The gateway picks it from the policy
/// agent id in the same way (src/mirsad/gateway.py).
Sector sectorForAgent(String agentId) {
  return switch (agentId) {
    'finance-assistant' => Sector.finance,
    'healthcare-assistant' => Sector.healthcare,
    _ => Sector.general,
  };
}

/// The `approve` flag of a decision request.
bool reviewDecisionToJson(ReviewDecision value) =>
    value == ReviewDecision.approve;
