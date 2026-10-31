import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

import '../../activity_fixtures.dart';

void main() {
  test('parses the contract example', () {
    final event = ActivityEventModel.fromJson(eventJson()).toEntity();

    expect(event.id, 'evt_0193');
    expect(event.decision, GatewayDecision.denied);
    expect(event.riskScore, 0.95);
    expect(event.createdAt, DateTime.utc(2026, 10, 29, 9, 12, 44));
  });

  test('reads every decision value', () {
    for (final decision in ['allowed', 'denied', 'held']) {
      final event = ActivityEventModel.fromJson(eventJson(decision: decision));
      expect(event.decision.name, decision);
    }
  });

  test('rejects an unknown decision', () {
    expect(
      () => ActivityEventModel.fromJson(eventJson(decision: 'paused')),
      throwsA(isA<DataFormatException>()),
    );
  });
}
