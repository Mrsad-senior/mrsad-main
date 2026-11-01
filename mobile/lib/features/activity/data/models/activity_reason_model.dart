import 'package:json_annotation/json_annotation.dart';

part 'activity_reason_model.g.dart';

/// One reason in a decision event's payload. Only the fields the feed uses
/// are read.
@JsonSerializable(createToJson: false)
class ActivityReasonModel {
  const ActivityReasonModel({required this.action, required this.message});

  factory ActivityReasonModel.fromJson(Map<String, dynamic> json) =>
      _$ActivityReasonModelFromJson(json);

  static const _severity = {'allow': 0, 'require_approval': 1, 'deny': 2};

  /// What this reason alone asks for: `allow`, `require_approval` or `deny`.
  final String action;

  /// The English explanation, shown as-is.
  final String message;

  int get severity => _severity[action] ?? 0;
}
