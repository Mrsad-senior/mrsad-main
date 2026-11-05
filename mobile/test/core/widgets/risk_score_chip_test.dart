import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/widgets/risk_score_chip.dart';

import '../../helpers/pump_app.dart';

void main() {
  test('RiskLevel.fromScore uses the 0.4 and 0.7 thresholds', () {
    expect(RiskLevel.fromScore(0.39), RiskLevel.low);
    expect(RiskLevel.fromScore(0.4), RiskLevel.medium);
    expect(RiskLevel.fromScore(0.69), RiskLevel.medium);
    expect(RiskLevel.fromScore(0.7), RiskLevel.high);
  });

  testWidgets('shows the level and percentage in English', (tester) async {
    await tester.pumpApp(const RiskScoreChip(score: 0.92));
    expect(find.text('High risk · 92%'), findsOneWidget);
  });

  testWidgets('shows the level and percentage in Arabic', (tester) async {
    await tester.pumpApp(
      const RiskScoreChip(score: 0.12),
      locale: const Locale('ar'),
    );
    expect(find.text('خطر منخفض · 12٪'), findsOneWidget);
  });
}
