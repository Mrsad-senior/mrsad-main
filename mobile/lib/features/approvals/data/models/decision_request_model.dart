import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';

part 'decision_request_model.g.dart';

/// Body of `POST /approvals/{id}`.
@JsonSerializable(createFactory: false, includeIfNull: false)
class DecisionRequestModel {
  const DecisionRequestModel({required this.decision, this.note});

  @JsonKey(toJson: reviewDecisionToJson)
  final ReviewDecision decision;

  final String? note;

  Map<String, dynamic> toJson() => _$DecisionRequestModelToJson(this);
}
