import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

import '../../activity_fixtures.dart';

void main() {
  test('parses a gateway decision event', () {
    final event = ActivityEventModel.fromJson(eventJson()).toEntity();

    expect(event.id, '193');
    expect(event.agentId, 'finance-assistant');
    expect(event.decision, GatewayDecision.denied);
    expect(event.riskScore, 0.95);
    expect(event.createdAt, DateTime.utc(2026, 10, 29, 9, 12, 44));
  });

  test('summarises with the first of the most severe reasons', () {
    final event = ActivityEventModel.fromJson(eventJson()).toEntity();
    expect(event.summary, 'The IBAN only appears in an invoice note.');
  });

  test('reads every decision action', () {
    const expected = {
      'allow': GatewayDecision.allowed,
      'deny': GatewayDecision.denied,
      'require_approval': GatewayDecision.held,
    };
    for (final MapEntry(:key, :value) in expected.entries) {
      final event = ActivityEventModel.fromJson(eventJson(action: key));
      expect(event.action, value);
    }
  });

  test('rejects an unknown action', () {
    expect(
      () => ActivityEventModel.fromJson(eventJson(action: 'pass')),
      throwsA(isA<DataFormatException>()),
    );
  });

  test('falls back to the risk band when the payload was trimmed', () {
    final event = ActivityEventModel.fromJson(
      eventJson(payload: {'_preview': '{"call": ...', '_truncated': true}),
    ).toEntity();

    expect(event.riskScore, 0.85);
    expect(event.summary, isEmpty);
  });
}
