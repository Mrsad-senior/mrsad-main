import 'package:equatable/equatable.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

/// One action an agent tried, and what the gateway decided.
class ActivityEvent extends Equatable {
  const ActivityEvent({
    required this.id,
    required this.agentId,
    required this.tool,
    required this.decision,
    required this.summary,
    required this.riskScore,
    required this.createdAt,
  });

  final String id;
  final String agentId;
  final String tool;
  final GatewayDecision decision;

  /// One or two sentences from the gateway, shown as-is.
  final String summary;

  /// Between 0 and 1.
  final double riskScore;

  final DateTime createdAt;

  @override
  List<Object?> get props => [
    id,
    agentId,
    tool,
    decision,
    summary,
    riskScore,
    createdAt,
  ];
}
