import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/detector/domain/entities/detection_span.dart';

part 'detection_span_model.g.dart';

/// `DetectionSpan` in src/mirsad/models.py.
@JsonSerializable(createToJson: false)
class DetectionSpanModel {
  const DetectionSpanModel({
    required this.start,
    required this.end,
    required this.text,
    this.ruleId,
  });

  factory DetectionSpanModel.fromJson(Map<String, dynamic> json) =>
      _$DetectionSpanModelFromJson(json);

  final int start;
  final int end;
  final String text;
  final String? ruleId;

  DetectionSpan toEntity() =>
      DetectionSpan(start: start, end: end, text: text, ruleId: ruleId);
}
