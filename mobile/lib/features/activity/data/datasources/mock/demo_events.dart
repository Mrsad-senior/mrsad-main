import 'package:mirsad/features/activity/data/models/activity_event_model.dart';
import 'package:mirsad/features/activity/data/models/activity_reason_model.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

/// The finance demo's decision events, newest first, timed relative to
/// [now]. Reasons use the gateway's wording, so a summary reads like the
/// real feed. All names, addresses and IBANs are fake.
List<ActivityEventModel> demoEvents(DateTime now) {
  DateTime ago(int minutes, [int seconds = 0]) =>
      now.subtract(Duration(minutes: minutes, seconds: seconds));

  return [
    ActivityEventModel(
      seq: 201,
      ts: ago(0, 15),
      agentId: 'finance-assistant',
      tool: 'transfer_funds',
      action: GatewayDecision.held,
      risk: 'critical',
      riskScore: 0.9,
      reasons: const [
        ActivityReasonModel(
          action: 'allow',
          message:
              "Tool 'transfer_funds' is classified as high risk (score 0.60).",
        ),
        ActivityReasonModel(
          action: 'require_approval',
          message:
              'Beneficiary is not in the trusted mock beneficiary registry.',
        ),
      ],
    ),
    ActivityEventModel(
      seq: 200,
      ts: ago(0, 25),
      agentId: 'finance-assistant',
      tool: 'get_account_balance',
      action: GatewayDecision.allowed,
      risk: 'low',
      riskScore: 0.04,
      reasons: const [
        ActivityReasonModel(
          action: 'allow',
          message:
              "Tool 'get_account_balance' is classified as low risk (score "
              '0.04).',
        ),
      ],
    ),
    ActivityEventModel(
      seq: 199,
      ts: ago(0, 35),
      agentId: 'finance-assistant',
      tool: 'send_email',
      action: GatewayDecision.held,
      risk: 'high',
      riskScore: 0.64,
      reasons: const [
        ActivityReasonModel(
          action: 'require_approval',
          message:
              "Argument 'to' sends data to freemail.example, outside the "
              "allowed domains ['bank.example'].",
        ),
      ],
    ),
    ActivityEventModel(
      seq: 198,
      ts: ago(6),
      agentId: 'finance-assistant',
      tool: 'export_customer_records',
      action: GatewayDecision.denied,
      risk: 'critical',
      riskScore: 0.98,
      reasons: const [
        ActivityReasonModel(
          action: 'deny',
          message:
              'A prompt-injection attempt was detected earlier in this '
              'conversation, and export_customer_records is a critical-risk '
              'action. Make sure the user really asked for it.',
        ),
      ],
    ),
    ActivityEventModel(
      seq: 197,
      ts: ago(14),
      agentId: 'finance-assistant',
      tool: 'send_email',
      action: GatewayDecision.allowed,
      risk: 'low',
      riskScore: 0.12,
      reasons: const [
        ActivityReasonModel(
          action: 'allow',
          message: "Tool 'send_email' is classified as low risk (score 0.12).",
        ),
      ],
    ),
    ActivityEventModel(
      seq: 196,
      ts: ago(31),
      agentId: 'finance-assistant',
      tool: 'update_beneficiary',
      action: GatewayDecision.denied,
      risk: 'critical',
      riskScore: 0.95,
      reasons: const [
        ActivityReasonModel(
          action: 'deny',
          message:
              'The destination SA******************7777 was not given by '
              'the user or by a trusted system: it only appears inside '
              'untrusted content (the "notes" field of a read_invoice '
              'result). An attacker may be redirecting update_beneficiary to '
              'an address they control.',
        ),
      ],
    ),
    ActivityEventModel(
      seq: 195,
      ts: ago(52),
      agentId: 'finance-assistant',
      tool: 'get_account_balance',
      action: GatewayDecision.allowed,
      risk: 'low',
      riskScore: 0.03,
      reasons: const [
        ActivityReasonModel(
          action: 'allow',
          message:
              "Tool 'get_account_balance' is classified as low risk (score "
              '0.03).',
        ),
      ],
    ),
  ];
}
