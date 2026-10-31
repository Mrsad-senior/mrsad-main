// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'activity_event_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ActivityEventModel _$ActivityEventModelFromJson(Map<String, dynamic> json) =>
    ActivityEventModel(
      id: json['id'] as String,
      agentId: json['agent_id'] as String,
      tool: json['tool'] as String,
      decision: gatewayDecisionFromJson(json['decision'] as String),
      summary: json['summary'] as String,
      riskScore: (json['risk_score'] as num).toDouble(),
      createdAt: DateTime.parse(json['created_at'] as String),
    );

Map<String, dynamic> _$ActivityEventModelToJson(ActivityEventModel instance) =>
    <String, dynamic>{
      'id': instance.id,
      'agent_id': instance.agentId,
      'tool': instance.tool,
      'decision': gatewayDecisionToJson(instance.decision),
      'summary': instance.summary,
      'risk_score': instance.riskScore,
      'created_at': instance.createdAt.toIso8601String(),
    };
