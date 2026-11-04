import 'dart:math';

import 'package:mirsad/features/detector/data/datasources/detector_data_source.dart';
import 'package:mirsad/features/detector/data/models/detection_result_model.dart';
import 'package:mirsad/features/detector/data/models/detection_span_model.dart';
import 'package:mirsad/features/detector/domain/entities/detection_label.dart';
import 'package:mirsad/features/detector/domain/entities/detection_language.dart';

/// A stand-in for the gateway's detector: a few phrase rules, in the
/// gateway's response shape, so the screen can be tried offline. It is not
/// the real detector and catches far less.
class DetectorMockDataSource implements DetectorDataSource {
  DetectorMockDataSource({this.latency = const Duration(milliseconds: 400)});

  /// Simulated network delay.
  final Duration latency;

  static final _rules = <(String, RegExp, double)>[
    (
      'override_instructions',
      RegExp(
        r'ignore (all )?(previous|prior|above) instructions',
        caseSensitive: false,
      ),
      0.95,
    ),
    ('override_instructions_ar', RegExp('تجاهل (جميع )?التعليمات'), 0.95),
    (
      'conceal_from_user',
      RegExp(r"(do not|don't) tell the user", caseSensitive: false),
      0.7,
    ),
    (
      'exfiltrate_data',
      RegExp(
        r'send (all )?(the )?(customer|account) (data|records)',
        caseSensitive: false,
      ),
      0.6,
    ),
  ];

  static final _arabic = RegExp('[\u0600-\u06FF]');
  static final _latin = RegExp('[A-Za-z]');

  @override
  Future<DetectionResultModel> scan(String text) async {
    await Future<void>.delayed(latency);
    final spans = <DetectionSpanModel>[];
    var score = 0.02;
    for (final (id, pattern, ruleScore) in _rules) {
      for (final match in pattern.allMatches(text)) {
        spans.add(
          DetectionSpanModel(
            start: match.start,
            end: match.end,
            text: match.group(0)!,
            ruleId: id,
          ),
        );
        score = max(score, ruleScore);
      }
    }
    return DetectionResultModel(
      score: score,
      label: score >= 0.8
          ? DetectionLabel.injection
          : score >= 0.5
          ? DetectionLabel.suspicious
          : DetectionLabel.benign,
      language: _languageOf(text),
      spans: spans,
    );
  }

  static DetectionLanguage _languageOf(String text) {
    final arabic = _arabic.hasMatch(text);
    final latin = _latin.hasMatch(text);
    if (arabic && latin) return DetectionLanguage.mixed;
    if (arabic) return DetectionLanguage.ar;
    if (latin) return DetectionLanguage.en;
    return DetectionLanguage.other;
  }
}
