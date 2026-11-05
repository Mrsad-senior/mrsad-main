import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/approvals/data/models/approval_reason_model.dart';

part 'call_decision_model.g.dart';

/// The gateway's verdict on the held tool call, stored on the approval as
/// `decision` (`Decision` in src/mirsad/models.py). Only the fields the app
/// uses are read.
@JsonSerializable(createToJson: false)
class CallDecisionModel {
  const CallDecisionModel({required this.riskScore, required this.reasons});

  factory CallDecisionModel.fromJson(Map<String, dynamic> json) =>
      _$CallDecisionModelFromJson(json);

  /// Between 0 and 1: the highest score of any reason.
  final double riskScore;

  /// Every layer's finding, including ones that allowed the call.
  final List<ApprovalReasonModel> reasons;
}
