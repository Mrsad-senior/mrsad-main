import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_reason.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

import '../../helpers/fake_clock.dart';

/// The demo's poisoned-invoice transfer, expiring 4:20 after [testNow].
Approval transferApproval({
  String id = 'apr_7f3c2a',
  ApprovalStatus status = ApprovalStatus.held,
  DateTime? expiresAt,
  String summaryEn = 'The banking assistant wants to transfer 50,000 SAR.',
  String summaryAr = 'يريد المساعد المصرفي تحويل 50,000 ريال.',
}) {
  return Approval(
    id: id,
    agentId: 'banking-assistant',
    sector: Sector.finance,
    tool: 'transfer_funds',
    arguments: const {
      'amount': 50000,
      'currency': 'SAR',
      'to_iban': 'SA4420000001234567891234',
      'reference': 'INV-2026-0419',
    },
    status: status,
    riskScore: 0.92,
    tainted: true,
    userTask: 'Process this supplier invoice',
    reasons: const [
      ApprovalReason(
        layer: ReasonLayer.intent,
        message: 'The user asked to process an invoice, not to pay a new IBAN.',
      ),
      ApprovalReason(
        layer: ReasonLayer.llmJudge,
        message: 'This matches payment-redirection fraud.',
      ),
    ],
    createdAt: testNow.subtract(const Duration(seconds: 40)),
    expiresAt:
        expiresAt ?? testNow.add(const Duration(minutes: 4, seconds: 20)),
    summaryEn: summaryEn,
    summaryAr: summaryAr,
  );
}

/// An approval record shaped like the gateway's (`ApprovalRecord` in
/// src/mirsad/models.py). The second reason's [layer] and [code] can be
/// swapped to try the layer mapping; [reasons] replaces all of them.
Map<String, dynamic> approvalJson({
  String status = 'pending',
  String agentId = 'finance-assistant',
  String layer = 'system',
  String code = 'SEMANTIC_TASK_MISMATCH',
  List<Map<String, dynamic>>? reasons,
  String? originalTask = 'Process this supplier invoice',
}) {
  final createdAt = DateTime.utc(2026, 10, 29, 9, 41, 7, 250);
  return {
    'id': 'apr_7f3c2a',
    'created_at': _epochSeconds(createdAt),
    'expires_at': _epochSeconds(createdAt.add(const Duration(minutes: 2))),
    'status': status,
    'agent_id': agentId,
    'session_id': 'conv-1',
    'call_id': 'call_0331e4c8903d4103',
    'tool': 'transfer_funds',
    'arguments': {
      'amount': 50000,
      'currency': 'SAR',
      'to_iban': 'SA******************1234',
    },
    'decision': {
      'call_id': 'call_0331e4c8903d4103',
      'action': 'require_approval',
      'reasons':
          reasons ??
          [
            reasonJson(
              layer: 'policy',
              code: 'TOOL_RISK',
              action: 'allow',
              message: "Tool 'transfer_funds' is classified as high risk.",
            ),
            reasonJson(layer: layer, code: code),
            reasonJson(
              layer: 'taint',
              code: 'TAINT_UNTRUSTED_DESTINATION',
              message: 'The IBAN only appears inside the invoice.',
            ),
          ],
      'risk': 'critical',
      'risk_score': 0.9,
      'sink': 'external',
      'policy_version': '6ca37e79',
      'approval_id': 'apr_7f3c2a',
      'approval_status': status,
      'latency_ms': 1.17,
      'audit_seq': 5,
    },
    'summary_en': 'The Finance Sandbox Agent wants to transfer money.',
    'summary_ar': 'يريد الوكيل تحويل أموال.',
    'risk': 'critical',
    'decided_by': null,
    'decided_at': null,
    'note': null,
    'original_task': ?originalTask,
  };
}

/// One entry of `decision.reasons`.
Map<String, dynamic> reasonJson({
  required String layer,
  required String code,
  String action = 'require_approval',
  String message = 'Not what the user asked for.',
}) {
  return {
    'layer': layer,
    'code': code,
    'message': message,
    'message_ar': null,
    'action': action,
    'rule_id': null,
    'risk_score': 0.9,
    'evidence': <String, dynamic>{},
  };
}

double _epochSeconds(DateTime time) =>
    time.microsecondsSinceEpoch / Duration.microsecondsPerSecond;
