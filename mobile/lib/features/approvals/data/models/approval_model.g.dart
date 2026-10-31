// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'approval_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ApprovalModel _$ApprovalModelFromJson(Map<String, dynamic> json) =>
    ApprovalModel(
      id: json['id'] as String,
      agentId: json['agent_id'] as String,
      sector: sectorFromJson(json['sector'] as String),
      tool: json['tool'] as String,
      arguments: json['arguments'] as Map<String, dynamic>,
      status: approvalStatusFromJson(json['status'] as String),
      riskScore: (json['risk_score'] as num).toDouble(),
      tainted: json['tainted'] as bool,
      userTask: json['user_task'] as String,
      reasons: (json['reasons'] as List<dynamic>)
          .map((e) => ApprovalReasonModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      createdAt: DateTime.parse(json['created_at'] as String),
      expiresAt: DateTime.parse(json['expires_at'] as String),
    );

Map<String, dynamic> _$ApprovalModelToJson(ApprovalModel instance) =>
    <String, dynamic>{
      'id': instance.id,
      'agent_id': instance.agentId,
      'sector': sectorToJson(instance.sector),
      'tool': instance.tool,
      'arguments': instance.arguments,
      'status': approvalStatusToJson(instance.status),
      'risk_score': instance.riskScore,
      'tainted': instance.tainted,
      'user_task': instance.userTask,
      'reasons': instance.reasons.map((e) => e.toJson()).toList(),
      'created_at': instance.createdAt.toIso8601String(),
      'expires_at': instance.expiresAt.toIso8601String(),
    };
