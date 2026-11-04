import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/home/data/models/tool_stats_model.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';

part 'overview_stats_model.g.dart';

/// `GET /api/stats/overview` (`Overview` in src/mirsad/api/routers/stats.py).
/// Only the fields the app uses are read.
@JsonSerializable(createToJson: false)
class OverviewStatsModel {
  const OverviewStatsModel({
    required this.hours,
    required this.totalCalls,
    required this.allowed,
    required this.denied,
    required this.approvalsRequired,
    required this.approvalsPending,
    required this.injectionsDetected,
    this.medianLatencyMs,
    this.p95LatencyMs,
    this.auditOk,
    this.byTool = const [],
  });

  factory OverviewStatsModel.fromJson(Map<String, dynamic> json) =>
      _$OverviewStatsModelFromJson(json);

  final double hours;
  final int totalCalls;
  final int allowed;
  final int denied;
  final int approvalsRequired;
  final int approvalsPending;
  final int injectionsDetected;
  final double? medianLatencyMs;
  final double? p95LatencyMs;
  final bool? auditOk;

  @JsonKey(defaultValue: [])
  final List<ToolStatsModel> byTool;

  OverviewStats toEntity() => OverviewStats(
    windowHours: hours,
    totalCalls: totalCalls,
    allowed: allowed,
    denied: denied,
    heldForReview: approvalsRequired,
    waitingNow: approvalsPending,
    injectionsDetected: injectionsDetected,
    auditOk: auditOk,
    medianLatencyMs: medianLatencyMs,
    p95LatencyMs: p95LatencyMs,
    tools: List.unmodifiable(byTool.map((tool) => tool.toEntity())),
  );
}
