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

/// The example event from docs/API_CONTRACT.md.
Map<String, dynamic> eventJson({String decision = 'denied'}) {
  return {
    'id': 'evt_0193',
    'agent_id': 'banking-assistant',
    'tool': 'update_beneficiary',
    'decision': decision,
    'summary': 'Blocked an instruction hidden in an invoice note.',
    'risk_score': 0.95,
    'created_at': '2026-10-29T09:12:44Z',
  };
}
