import 'package:equatable/equatable.dart';

/// A passage of the scanned text that a detector rule matched.
class DetectionSpan extends Equatable {
  const DetectionSpan({
    required this.start,
    required this.end,
    required this.text,
    this.ruleId,
  });

  /// Offsets into the scanned text.
  final int start;
  final int end;

  final String text;

  /// The rule that matched, e.g. `override_instructions`.
  final String? ruleId;

  @override
  List<Object?> get props => [start, end, text, ruleId];
}
