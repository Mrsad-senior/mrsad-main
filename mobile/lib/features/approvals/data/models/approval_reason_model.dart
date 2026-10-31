import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_reason.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';

part 'approval_reason_model.g.dart';

@JsonSerializable()
class ApprovalReasonModel {
  const ApprovalReasonModel({required this.layer, required this.message});

  factory ApprovalReasonModel.fromJson(Map<String, dynamic> json) =>
      _$ApprovalReasonModelFromJson(json);

  @JsonKey(fromJson: reasonLayerFromJson, toJson: reasonLayerToJson)
  final ReasonLayer layer;

  final String message;

  Map<String, dynamic> toJson() => _$ApprovalReasonModelToJson(this);

  ApprovalReason toEntity() => ApprovalReason(layer: layer, message: message);
}
