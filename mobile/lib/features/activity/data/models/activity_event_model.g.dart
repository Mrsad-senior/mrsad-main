// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'activity_event_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ActivityEventModel _$ActivityEventModelFromJson(Map<String, dynamic> json) =>
    ActivityEventModel(
      seq: (json['seq'] as num).toInt(),
      ts: dateTimeFromEpochSeconds(json['ts'] as num),
      action: gatewayDecisionFromJson(json['action'] as String),
      reasons:
          (_readPayload(json, 'reasons') as List<dynamic>?)
              ?.map(
                (e) => ActivityReasonModel.fromJson(e as Map<String, dynamic>),
              )
              .toList() ??
          [],
      agentId: json['agent_id'] as String?,
      tool: json['tool'] as String?,
      risk: json['risk'] as String?,
      riskScore: (_readPayload(json, 'risk_score') as num?)?.toDouble(),
    );
