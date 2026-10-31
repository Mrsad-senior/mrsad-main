import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

part 'activity_event_model.g.dart';

/// An event as the gateway API and the Supabase `events` table send it.
@JsonSerializable()
class ActivityEventModel {
  const ActivityEventModel({
    required this.id,
    required this.agentId,
    required this.tool,
    required this.decision,
    required this.summary,
    required this.riskScore,
    required this.createdAt,
  });

  factory ActivityEventModel.fromJson(Map<String, dynamic> json) =>
      _$ActivityEventModelFromJson(json);

  final String id;
  final String agentId;
  final String tool;

  @JsonKey(fromJson: gatewayDecisionFromJson, toJson: gatewayDecisionToJson)
  final GatewayDecision decision;

  final String summary;
  final double riskScore;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => _$ActivityEventModelToJson(this);

  ActivityEvent toEntity() {
    return ActivityEvent(
      id: id,
      agentId: agentId,
      tool: tool,
      decision: decision,
      summary: summary,
      riskScore: riskScore,
      createdAt: createdAt,
    );
  }
}

/// The JSON values match the enum names: `allowed`, `denied`, `held`.
GatewayDecision gatewayDecisionFromJson(String value) {
  return GatewayDecision.values.asNameMap()[value] ??
      (throw DataFormatException('Unknown decision "$value"'));
}

String gatewayDecisionToJson(GatewayDecision value) => value.name;
