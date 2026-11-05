// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'tool_stats_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ToolStatsModel _$ToolStatsModelFromJson(Map<String, dynamic> json) =>
    ToolStatsModel(
      tool: json['tool'] as String,
      allowed: (json['allowed'] as num?)?.toInt() ?? 0,
      denied: (json['denied'] as num?)?.toInt() ?? 0,
      approval: (json['approval'] as num?)?.toInt() ?? 0,
    );
