import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

import '../../helpers/fake_clock.dart';

ActivityEvent activityEvent({
  String id = 'evt_1',
  GatewayDecision decision = GatewayDecision.denied,
  Duration age = Duration.zero,
}) {
  return ActivityEvent(
    id: id,
    agentId: 'banking-assistant',
    tool: 'update_beneficiary',
    decision: decision,
    summary: 'Blocked an injected instruction to change the beneficiary.',
    riskScore: 0.95,
    createdAt: testNow.subtract(age),
  );
}

/// A `tool_call.decision` audit event shaped like the gateway's
/// (`AuditEvent` in src/mirsad/models.py). [payload] replaces the default.
Map<String, dynamic> eventJson({
  String action = 'deny',
  Map<String, dynamic>? payload,
}) {
  final ts = DateTime.utc(2026, 10, 29, 9, 12, 44);
  return {
    'seq': 193,
    'ts': ts.millisecondsSinceEpoch / Duration.millisecondsPerSecond,
    'event_type': 'tool_call.decision',
    'session_id': 'conv-1',
    'agent_id': 'finance-assistant',
    'tool': 'update_beneficiary',
    'call_id': 'call_4dd7b47cc4144ffa',
    'action': action,
    'risk': 'critical',
    'policy_version': '6ca37e79',
    'payload':
        payload ??
        {
          'risk_score': 0.95,
          'latency_ms': 1.17,
          'reasons': [
            _reason('allow', "Tool 'update_beneficiary' is high risk."),
            _reason('require_approval', 'Untrusted content was read earlier.'),
            _reason('deny', 'The IBAN only appears in an invoice note.'),
            _reason('deny', 'A second denial, not the summary.'),
          ],
        },
    'prev_hash': '0' * 64,
    'hash': 'f' * 64,
  };
}

Map<String, dynamic> _reason(String action, String message) {
  return {
    'layer': 'taint',
    'code': 'TAINT_UNTRUSTED_DESTINATION',
    'action': action,
    'message': message,
    'message_ar': null,
  };
}
