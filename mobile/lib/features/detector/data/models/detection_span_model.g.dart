// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'detection_span_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

DetectionSpanModel _$DetectionSpanModelFromJson(Map<String, dynamic> json) =>
    DetectionSpanModel(
      start: (json['start'] as num).toInt(),
      end: (json['end'] as num).toInt(),
      text: json['text'] as String,
      ruleId: json['rule_id'] as String?,
    );
