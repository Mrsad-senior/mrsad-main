import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/widgets/status_badge.dart';

/// How worrying a 0-1 risk score is.
enum RiskLevel {
  low,
  medium,
  high;

  static const double mediumFrom = 0.4;
  static const double highFrom = 0.7;

  static RiskLevel fromScore(double score) {
    if (score >= highFrom) return RiskLevel.high;
    if (score >= mediumFrom) return RiskLevel.medium;
    return RiskLevel.low;
  }
}

/// Shows a risk score as "High risk · 92%", colored by its level.
class RiskScoreChip extends StatelessWidget {
  const RiskScoreChip({required this.score, super.key});

  /// Between 0 and 1.
  final double score;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final level = RiskLevel.fromScore(score);
    final percent = (score.clamp(0, 1) * 100).round();
    final (label, tone) = switch (level) {
      RiskLevel.low => (l10n.riskLow, StatusTone.positive),
      RiskLevel.medium => (l10n.riskMedium, StatusTone.warning),
      RiskLevel.high => (l10n.riskHigh, StatusTone.negative),
    };
    return StatusBadge(
      label: l10n.riskScore(label, percent),
      tone: tone,
      icon: Icons.speed,
    );
  }
}
