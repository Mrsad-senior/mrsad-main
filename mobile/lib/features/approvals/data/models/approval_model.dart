import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/core/network/epoch_seconds.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/data/models/call_decision_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';

part 'approval_model.g.dart';

/// An approval record as `GET /api/approvals` and `GET /api/approvals/{id}`
/// send it (`ApprovalRecord` in src/mirsad/models.py). Only the fields the
/// app uses are read.
///
/// The gateway stores the arguments redacted: an IBAN keeps its country code
/// and last four characters (`SA******************1234`).
@JsonSerializable(createToJson: false)
class ApprovalModel {
  const ApprovalModel({
    required this.id,
    required this.agentId,
    required this.tool,
    required this.arguments,
    required this.status,
    required this.decision,
    required this.createdAt,
    required this.expiresAt,
    this.summaryEn = '',
    this.summaryAr = '',
    this.originalTask,
  });

  factory ApprovalModel.fromJson(Map<String, dynamic> json) =>
      _$ApprovalModelFromJson(json);

  final String id;

  /// The policy agent id, e.g. `finance-assistant`.
  final String agentId;

  final String tool;
  final Map<String, dynamic> arguments;

  @JsonKey(fromJson: approvalStatusFromJson)
  final ApprovalStatus status;

  final CallDecisionModel decision;

  @JsonKey(fromJson: dateTimeFromEpochSeconds)
  final DateTime createdAt;

  @JsonKey(fromJson: dateTimeFromEpochSeconds)
  final DateTime expiresAt;

  /// The gateway's plain-language summary in English and Arabic
  /// (src/mirsad/approvals/summary.py). Empty when it has none.
  @JsonKey(defaultValue: '')
  final String summaryEn;

  @JsonKey(defaultValue: '')
  final String summaryAr;

  /// What the user asked the agent to do. Proposed in docs/API_CONTRACT.md:
  /// the gateway does not send it yet.
  final String? originalTask;

  ApprovalModel copyWith({ApprovalStatus? status}) {
    return ApprovalModel(
      id: id,
      agentId: agentId,
      tool: tool,
      arguments: arguments,
      status: status ?? this.status,
      decision: decision,
      createdAt: createdAt,
      expiresAt: expiresAt,
      summaryEn: summaryEn,
      summaryAr: summaryAr,
      originalTask: originalTask,
    );
  }

  Approval toEntity() {
    final objections = decision.reasons.where((reason) => reason.objects);
    return Approval(
      id: id,
      agentId: agentId,
      sector: sectorForAgent(agentId),
      tool: tool,
      arguments: Map.unmodifiable(arguments),
      status: status,
      riskScore: decision.riskScore,
      tainted: objections.any((reason) => reason.untrustedInput),
      userTask: originalTask ?? '',
      reasons: List.unmodifiable(objections.map((reason) => reason.toEntity())),
      createdAt: createdAt,
      expiresAt: expiresAt,
      summaryEn: summaryEn,
      summaryAr: summaryAr,
    );
  }
}
