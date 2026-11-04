import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/approval_reason_model.dart';
import 'package:mirsad/features/approvals/data/models/call_decision_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';

/// How long the gateway holds an action before it expires
/// (`MIRSAD_APPROVAL_TIMEOUT_S`, 120 seconds by default).
const Duration approvalWindow = Duration(minutes: 2);

/// The finance demo's held actions, timed relative to [now]. They are shaped
/// like the gateway's records: arguments redacted the way the gateway stores
/// them, reasons with its layers, codes and wording. All names, addresses and
/// IBANs are fake.
List<ApprovalModel> demoApprovals(DateTime now) {
  final invoiceHeldAt = now.subtract(const Duration(seconds: 15));
  final statementHeldAt = now.subtract(const Duration(seconds: 35));
  return [
    ApprovalModel(
      id: 'apr_7f3c2a',
      agentId: 'finance-assistant',
      tool: 'transfer_funds',
      arguments: const {
        'amount': 50000,
        'currency': 'SAR',
        'to_iban': 'SA******************1234',
        'beneficiary_name': 'Gulf Office Supplies Co.',
        'reference': 'INV-2026-0419',
      },
      status: ApprovalStatus.held,
      decision: const CallDecisionModel(
        riskScore: 0.9,
        reasons: [
          ApprovalReasonModel(
            layer: 'policy',
            code: 'TOOL_RISK',
            action: 'allow',
            message:
                "Tool 'transfer_funds' is classified as high risk (score "
                '0.60).',
          ),
          ApprovalReasonModel(
            layer: 'system',
            code: 'SEMANTIC_TASK_MISMATCH',
            action: 'require_approval',
            message:
                'Local semantic intent judge: the user asked to process an '
                'invoice, not to pay a beneficiary named only inside it.',
          ),
          ApprovalReasonModel(
            layer: 'taint',
            code: 'TAINT_UNTRUSTED_DESTINATION',
            action: 'require_approval',
            message:
                'The destination SA******************1234 was not given by '
                'the user or by a trusted system: it only appears inside '
                'untrusted content (the "body" field of a read_invoice '
                'result). An attacker may be redirecting transfer_funds to an '
                'address they control.',
          ),
          ApprovalReasonModel(
            layer: 'system',
            code: 'NEW_BENEFICIARY',
            action: 'require_approval',
            message:
                'Beneficiary is not in the trusted mock beneficiary registry.',
          ),
        ],
      ),
      createdAt: invoiceHeldAt,
      expiresAt: invoiceHeldAt.add(approvalWindow),
      summaryEn:
          'The finance assistant wants to transfer 50,000 SAR to '
          'SA******************1234. Mirsad paused it because that account '
          'only appears inside an invoice it read, and the beneficiary is '
          'new. Risk: critical.',
      summaryAr:
          'يريد المساعد المالي تحويل 50,000 ريال إلى الحساب '
          'SA******************1234. أوقفه مرصاد لأن هذا الحساب ورد فقط داخل '
          'فاتورة قرأها، والمستفيد جديد. مستوى الخطر: حرج.',
      originalTask: 'Process this supplier invoice',
    ),
    ApprovalModel(
      id: 'apr_2b91e4',
      agentId: 'finance-assistant',
      tool: 'send_email',
      arguments: const {
        'to': 'statements@freemail.example',
        'subject': 'Your October account statement',
        'attachments': ['statement_2026-10_acct-4471.pdf'],
        'body': 'Dear customer, please find your October statement attached.',
      },
      status: ApprovalStatus.held,
      decision: const CallDecisionModel(
        riskScore: 0.64,
        reasons: [
          ApprovalReasonModel(
            layer: 'policy',
            code: 'CONSTRAINT_VIOLATION',
            action: 'require_approval',
            message:
                "Argument 'to' sends data to freemail.example, outside the "
                "allowed domains ['bank.example'].",
          ),
          ApprovalReasonModel(
            layer: 'taint',
            code: 'TAINT_CONFIDENTIAL_TO_EXTERNAL',
            action: 'require_approval',
            message:
                'send_email would send confidential data outside the '
                'organisation: the account number ****4471 comes from a '
                'get_account_balance result.',
          ),
        ],
      ),
      createdAt: statementHeldAt,
      expiresAt: statementHeldAt.add(approvalWindow),
      summaryEn:
          'The finance assistant wants to email a customer statement to '
          'statements@freemail.example. Mirsad paused it because the address '
          'is outside the bank and the email carries an account number. '
          'Risk: medium.',
      summaryAr:
          'يريد المساعد المالي إرسال كشف حساب عميل بالبريد إلى '
          'statements@freemail.example. أوقفه مرصاد لأن العنوان خارج البنك '
          'والرسالة تحمل رقم حساب. مستوى الخطر: متوسط.',
      originalTask: 'Send customer #48213 their October statement',
    ),
  ];
}
