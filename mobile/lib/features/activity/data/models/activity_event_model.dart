import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/epoch_seconds.dart';
import 'package:mirsad/features/activity/data/models/activity_reason_model.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

part 'activity_event_model.g.dart';

/// A `tool_call.decision` audit event, as `GET /api/audit/events` sends it
/// (`AuditEvent` in src/mirsad/models.py). The risk score and the reasons sit
/// in its payload. Only the fields the feed uses are read.
@JsonSerializable(createToJson: false)
class ActivityEventModel {
  const ActivityEventModel({
    required this.seq,
    required this.ts,
    required this.action,
    required this.reasons,
    this.agentId,
    this.tool,
    this.risk,
    this.riskScore,
  });

  factory ActivityEventModel.fromJson(Map<String, dynamic> json) =>
      _$ActivityEventModelFromJson(json);

  /// The audit event type the feed shows: the gateway deciding a tool call.
  static const eventType = 'tool_call.decision';

  /// The event's number in the audit chain, unique, so it serves as the id.
  final int seq;

  @JsonKey(fromJson: dateTimeFromEpochSeconds)
  final DateTime ts;

  final String? agentId;
  final String? tool;

  /// The gateway's decision, made before any human was asked.
  @JsonKey(fromJson: gatewayDecisionFromJson)
  final GatewayDecision action;

  /// `low`, `medium`, `high` or `critical`.
  final String? risk;

  /// Between 0 and 1. Missing when the gateway trimmed an oversized payload.
  @JsonKey(readValue: _readPayload)
  final double? riskScore;

  @JsonKey(readValue: _readPayload, defaultValue: [])
  final List<ActivityReasonModel> reasons;

  ActivityEvent toEntity() {
    return ActivityEvent(
      id: '$seq',
      agentId: agentId ?? '',
      tool: tool ?? '',
      decision: action,
      summary: _decidingReason?.message ?? '',
      riskScore: riskScore ?? _lowestScoreOf(risk),
      createdAt: ts,
    );
  }

  /// The first of the most severe reasons: the one that set the decision.
  ActivityReasonModel? get _decidingReason {
    ActivityReasonModel? deciding;
    for (final reason in reasons) {
      if (deciding == null || reason.severity > deciding.severity) {
        deciding = reason;
      }
    }
    return deciding;
  }
}

/// `action` of a decision event.
GatewayDecision gatewayDecisionFromJson(String value) {
  return switch (value) {
    'allow' => GatewayDecision.allowed,
    'deny' => GatewayDecision.denied,
    'require_approval' => GatewayDecision.held,
    _ => throw DataFormatException('Unknown decision "$value"'),
  };
}

Object? _readPayload(Map<dynamic, dynamic> json, String key) {
  final payload = json['payload'];
  return payload is Map ? payload[key] : null;
}

/// The lowest score in a risk band (`Risk.from_score` in src/mirsad/models.py).
double _lowestScoreOf(String? risk) {
  return switch (risk) {
    'critical' => 0.85,
    'high' => 0.6,
    'medium' => 0.3,
    _ => 0,
  };
}
