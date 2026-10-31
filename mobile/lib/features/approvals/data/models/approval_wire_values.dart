import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

// The JSON spelling of each enum value, as listed in docs/API_CONTRACT.md.
// Kept here so the domain enums stay free of JSON concerns.

const Map<Sector, String> _sectors = {
  Sector.finance: 'finance',
  Sector.healthcare: 'healthcare',
  Sector.general: 'general',
};

const Map<ApprovalStatus, String> _statuses = {
  ApprovalStatus.held: 'held',
  ApprovalStatus.approved: 'approved',
  ApprovalStatus.rejected: 'rejected',
  ApprovalStatus.expired: 'expired',
};

const Map<ReasonLayer, String> _layers = {
  ReasonLayer.policy: 'policy',
  ReasonLayer.taint: 'taint',
  ReasonLayer.intent: 'intent',
  ReasonLayer.llmJudge: 'llm_judge',
  ReasonLayer.keywords: 'keywords',
  ReasonLayer.other: 'other',
};

const Map<ReviewDecision, String> _decisions = {
  ReviewDecision.approve: 'approve',
  ReviewDecision.reject: 'reject',
};

Sector sectorFromJson(String value) => _decode(_sectors, value, 'sector');

String sectorToJson(Sector value) => _sectors[value]!;

ApprovalStatus approvalStatusFromJson(String value) =>
    _decode(_statuses, value, 'status');

String approvalStatusToJson(ApprovalStatus value) => _statuses[value]!;

/// Unknown layers become [ReasonLayer.other], so a new gateway layer does not
/// break the app.
ReasonLayer reasonLayerFromJson(String value) =>
    _lookup(_layers, value) ?? ReasonLayer.other;

String reasonLayerToJson(ReasonLayer value) => _layers[value]!;

String reviewDecisionToJson(ReviewDecision value) => _decisions[value]!;

T _decode<T>(Map<T, String> values, String wire, String field) {
  return _lookup(values, wire) ??
      (throw DataFormatException('Unknown $field "$wire"'));
}

T? _lookup<T>(Map<T, String> values, String wire) {
  for (final MapEntry(:key, :value) in values.entries) {
    if (value == wire) return key;
  }
  return null;
}
