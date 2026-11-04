import 'package:equatable/equatable.dart';
import 'package:mirsad/features/detector/domain/entities/detection_label.dart';
import 'package:mirsad/features/detector/domain/entities/detection_language.dart';
import 'package:mirsad/features/detector/domain/entities/detection_span.dart';

/// What Mirsad's prompt-injection detector made of a text.
class DetectionResult extends Equatable {
  const DetectionResult({
    required this.score,
    required this.label,
    required this.language,
    this.spans = const [],
    this.signals = const [],
  });

  /// Between 0 and 1.
  final double score;

  final DetectionLabel label;
  final DetectionLanguage language;

  /// The passages the detector's rules matched.
  final List<DetectionSpan> spans;

  /// Evasion tricks it noticed while normalising the text, e.g.
  /// `zero_width_chars`.
  final List<String> signals;

  @override
  List<Object?> get props => [score, label, language, spans, signals];
}
