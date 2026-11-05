// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'detection_result_model.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

DetectionResultModel _$DetectionResultModelFromJson(
  Map<String, dynamic> json,
) => DetectionResultModel(
  score: (json['score'] as num).toDouble(),
  label: _labelFromJson(json['label'] as String),
  language: _languageFromJson(json['language'] as String),
  spans:
      (json['spans'] as List<dynamic>?)
          ?.map((e) => DetectionSpanModel.fromJson(e as Map<String, dynamic>))
          .toList() ??
      [],
  signals:
      (json['signals'] as List<dynamic>?)?.map((e) => e as String).toList() ??
      [],
);
