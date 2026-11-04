// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'overview_stats_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

OverviewStatsModel _$OverviewStatsModelFromJson(Map<String, dynamic> json) =>
    OverviewStatsModel(
      hours: (json['hours'] as num).toDouble(),
      totalCalls: (json['total_calls'] as num).toInt(),
      allowed: (json['allowed'] as num).toInt(),
      denied: (json['denied'] as num).toInt(),
      approvalsRequired: (json['approvals_required'] as num).toInt(),
      approvalsPending: (json['approvals_pending'] as num).toInt(),
      injectionsDetected: (json['injections_detected'] as num).toInt(),
      medianLatencyMs: (json['median_latency_ms'] as num?)?.toDouble(),
      p95LatencyMs: (json['p95_latency_ms'] as num?)?.toDouble(),
      auditOk: json['audit_ok'] as bool?,
      byTool:
          (json['by_tool'] as List<dynamic>?)
              ?.map((e) => ToolStatsModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
