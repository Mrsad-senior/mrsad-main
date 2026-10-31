// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'approval_reason_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

ApprovalReasonModel _$ApprovalReasonModelFromJson(Map<String, dynamic> json) =>
    ApprovalReasonModel(
      layer: reasonLayerFromJson(json['layer'] as String),
      message: json['message'] as String,
    );

Map<String, dynamic> _$ApprovalReasonModelToJson(
  ApprovalReasonModel instance,
) => <String, dynamic>{
  'layer': reasonLayerToJson(instance.layer),
  'message': instance.message,
};
