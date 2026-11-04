import 'package:equatable/equatable.dart';
import 'package:mirsad/features/home/domain/entities/tool_activity.dart';

/// What the gateway did over a recent window (`GET /api/stats/overview`).
class OverviewStats extends Equatable {
  const OverviewStats({
    required this.windowHours,
    required this.totalCalls,
    required this.allowed,
    required this.denied,
    required this.heldForReview,
    required this.waitingNow,
    required this.injectionsDetected,
    required this.auditOk,
    this.medianLatencyMs,
    this.p95LatencyMs,
    this.tools = const [],
  });

  /// How far back the figures go.
  final double windowHours;

  /// Tool calls the gateway decided on.
  final int totalCalls;

  final int allowed;
  final int denied;

  /// Calls that needed a human, whatever the human then decided.
  final int heldForReview;

  /// Held actions still waiting for a decision right now.
  final int waitingNow;

  /// Prompt injections the detector caught in tool results.
  final int injectionsDetected;

  /// Whether the audit hash chain verified. Null when the gateway could not
  /// check it.
  final bool? auditOk;

  /// The gateway's own decision time; null without any calls.
  final double? medianLatencyMs;
  final double? p95LatencyMs;

  /// Calls per tool.
  final List<ToolActivity> tools;

  /// The [count] tools with the most calls, busiest first.
  List<ToolActivity> busiestTools([int count = 3]) {
    final sorted = [...tools]..sort((a, b) => b.total.compareTo(a.total));
    return sorted.take(count).toList();
  }

  @override
  List<Object?> get props => [
    windowHours,
    totalCalls,
    allowed,
    denied,
    heldForReview,
    waitingNow,
    injectionsDetected,
    auditOk,
    medianLatencyMs,
    p95LatencyMs,
    tools,
  ];
}
