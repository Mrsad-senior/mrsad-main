import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_reason.dart';

part 'approval_reason_model.g.dart';

/// One entry of `decision.reasons` on an approval record (`Reason` in
/// src/mirsad/models.py). Only the fields the app uses are read.
@JsonSerializable(createToJson: false)
class ApprovalReasonModel {
  const ApprovalReasonModel({
    required this.layer,
    required this.code,
    required this.action,
    required this.message,
  });

  factory ApprovalReasonModel.fromJson(Map<String, dynamic> json) =>
      _$ApprovalReasonModelFromJson(json);

  /// `policy`, `ratelimit`, `taint`, `detector`, `approval` or `system`.
  final String layer;

  /// The rule that produced it, e.g. `TAINT_UNTRUSTED_DESTINATION`.
  final String code;

  /// What this reason alone asks for: `allow`, `require_approval` or `deny`.
  final String action;

  /// The English explanation, shown as-is.
  final String message;

  /// Whether it objected to the call. Reasons that only allow it, such as
  /// the tool's base risk, are not shown to the reviewer.
  bool get objects => action != allowAction;

  /// Whether it reports untrusted content reaching the call.
  bool get untrustedInput =>
      objects && layer == 'taint' && untrustedTaintCodes.contains(code);

  ApprovalReason toEntity() {
    return ApprovalReason(
      layer: reasonLayerFromWire(layer, code),
      message: message,
    );
  }
}
