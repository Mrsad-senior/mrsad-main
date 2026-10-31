import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/approvals/data/models/approval_reason_model.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

part 'approval_model.g.dart';

/// An approval as the gateway API and the Supabase `approvals` table send it.
@JsonSerializable()
class ApprovalModel {
  const ApprovalModel({
    required this.id,
    required this.agentId,
    required this.sector,
    required this.tool,
    required this.arguments,
    required this.status,
    required this.riskScore,
    required this.tainted,
    required this.userTask,
    required this.reasons,
    required this.createdAt,
    required this.expiresAt,
  });

  factory ApprovalModel.fromJson(Map<String, dynamic> json) =>
      _$ApprovalModelFromJson(json);

  final String id;
  final String agentId;

  @JsonKey(fromJson: sectorFromJson, toJson: sectorToJson)
  final Sector sector;

  final String tool;
  final Map<String, dynamic> arguments;

  @JsonKey(fromJson: approvalStatusFromJson, toJson: approvalStatusToJson)
  final ApprovalStatus status;

  final double riskScore;
  final bool tainted;
  final String userTask;
  final List<ApprovalReasonModel> reasons;
  final DateTime createdAt;
  final DateTime expiresAt;

  Map<String, dynamic> toJson() => _$ApprovalModelToJson(this);

  ApprovalModel copyWith({ApprovalStatus? status}) {
    return ApprovalModel(
      id: id,
      agentId: agentId,
      sector: sector,
      tool: tool,
      arguments: arguments,
      status: status ?? this.status,
      riskScore: riskScore,
      tainted: tainted,
      userTask: userTask,
      reasons: reasons,
      createdAt: createdAt,
      expiresAt: expiresAt,
    );
  }

  Approval toEntity() {
    return Approval(
      id: id,
      agentId: agentId,
      sector: sector,
      tool: tool,
      arguments: Map.unmodifiable(arguments),
      status: status,
      riskScore: riskScore,
      tainted: tainted,
      userTask: userTask,
      reasons: List.unmodifiable(reasons.map((reason) => reason.toEntity())),
      createdAt: createdAt,
      expiresAt: expiresAt,
    );
  }
}
