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
  );
}

/// The example approval from docs/API_CONTRACT.md.
Map<String, dynamic> approvalJson({
  String status = 'held',
  String layer = 'intent',
}) {
  return {
    'id': 'apr_7f3c2a',
    'agent_id': 'banking-assistant',
    'sector': 'finance',
    'tool': 'transfer_funds',
    'arguments': {
      'amount': 50000,
      'currency': 'SAR',
      'to_iban': 'SA4420000001234567891234',
    },
    'status': status,
    'risk_score': 0.92,
    'tainted': true,
    'user_task': 'Process this supplier invoice',
    'reasons': [
      {'layer': layer, 'message': 'Not what the user asked for.'},
      {'layer': 'llm_judge', 'message': 'Looks like payment redirection.'},
    ],
    'created_at': '2026-10-29T09:41:07Z',
    'expires_at': '2026-10-29T09:46:07Z',
  };
}
