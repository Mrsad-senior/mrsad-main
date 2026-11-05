import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/detector/data/models/detection_span_model.dart';
import 'package:mirsad/features/detector/domain/entities/detection_label.dart';
import 'package:mirsad/features/detector/domain/entities/detection_language.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';

part 'detection_result_model.g.dart';

/// `DetectionResult` in src/mirsad/models.py, as `POST /api/detector/scan`
/// returns it. Only the fields the app uses are read.
@JsonSerializable(createToJson: false)
class DetectionResultModel {
  const DetectionResultModel({
    required this.score,
    required this.label,
    required this.language,
    this.spans = const [],
    this.signals = const [],
  });

  factory DetectionResultModel.fromJson(Map<String, dynamic> json) =>
      _$DetectionResultModelFromJson(json);

  final double score;

  @JsonKey(fromJson: _labelFromJson)
  final DetectionLabel label;

  @JsonKey(fromJson: _languageFromJson)
  final DetectionLanguage language;

  @JsonKey(defaultValue: [])
  final List<DetectionSpanModel> spans;

  @JsonKey(defaultValue: [])
  final List<String> signals;

  DetectionResult toEntity() => DetectionResult(
    score: score,
    label: label,
    language: language,
    spans: List.unmodifiable(spans.map((span) => span.toEntity())),
    signals: List.unmodifiable(signals),
  );
}

/// An unknown label is a format error rather than a guess about safety.
DetectionLabel _labelFromJson(String value) =>
    DetectionLabel.values.asNameMap()[value] ??
    (throw FormatException('Unknown detection label "$value"'));

DetectionLanguage _languageFromJson(String value) =>
    DetectionLanguage.values.asNameMap()[value] ?? DetectionLanguage.other;
