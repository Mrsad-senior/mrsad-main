import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/home/domain/entities/tool_activity.dart';

part 'tool_stats_model.g.dart';

/// One entry of the overview's `by_tool` (`ToolStats` in the gateway).
@JsonSerializable(createToJson: false)
class ToolStatsModel {
  const ToolStatsModel({
    required this.tool,
    this.allowed = 0,
    this.denied = 0,
    this.approval = 0,
  });

  factory ToolStatsModel.fromJson(Map<String, dynamic> json) =>
      _$ToolStatsModelFromJson(json);

  final String tool;
  final int allowed;
  final int denied;

  /// Calls that needed approval, whatever the approver decided.
  final int approval;

  ToolActivity toEntity() => ToolActivity(
    tool: tool,
    allowed: allowed,
    denied: denied,
    held: approval,
  );
}
