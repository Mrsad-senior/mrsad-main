// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'approval_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ApprovalModel _$ApprovalModelFromJson(Map<String, dynamic> json) =>
    ApprovalModel(
      id: json['id'] as String,
      agentId: json['agent_id'] as String,
      tool: json['tool'] as String,
      arguments: json['arguments'] as Map<String, dynamic>,
      status: approvalStatusFromJson(json['status'] as String),
      decision: CallDecisionModel.fromJson(
        json['decision'] as Map<String, dynamic>,
      ),
      createdAt: dateTimeFromEpochSeconds(json['created_at'] as num),
      expiresAt: dateTimeFromEpochSeconds(json['expires_at'] as num),
      originalTask: json['original_task'] as String?,
    );
