import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/approval_reason_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

/// How long the gateway holds an action before auto-rejecting it.
const Duration approvalWindow = Duration(minutes: 5);

/// The finance demo's held actions, timed relative to [now]. All names,
/// addresses and IBANs are fake.
List<ApprovalModel> demoApprovals(DateTime now) {
  final invoiceHeldAt = now.subtract(const Duration(seconds: 40));
  final statementHeldAt = now.subtract(const Duration(minutes: 1, seconds: 50));
  return [
    ApprovalModel(
      id: 'apr_7f3c2a',
      agentId: 'banking-assistant',
      sector: Sector.finance,
      tool: 'transfer_funds',
      arguments: const {
        'amount': 50000,
        'currency': 'SAR',
        'to_iban': 'SA4420000001234567891234',
        'beneficiary_name': 'Gulf Office Supplies Co.',
        'reference': 'INV-2026-0419',
      },
      status: ApprovalStatus.held,
      riskScore: 0.92,
      tainted: true,
      userTask: 'Process this supplier invoice',
      reasons: const [
        ApprovalReasonModel(
          layer: ReasonLayer.intent,
          message:
              'The user asked to process an invoice, not to pay a new '
              'beneficiary. This IBAN has never been paid before and is not '
              "on the supplier's record.",
        ),
        ApprovalReasonModel(
          layer: ReasonLayer.llmJudge,
          message:
              'The IBAN only appears in text extracted from the invoice PDF, '
              'which is untrusted. The request matches payment-redirection '
              'fraud.',
        ),
      ],
      createdAt: invoiceHeldAt,
      expiresAt: invoiceHeldAt.add(approvalWindow),
    ),
    ApprovalModel(
      id: 'apr_2b91e4',
      agentId: 'customer-service-agent',
      sector: Sector.finance,
      tool: 'send_email',
      arguments: const {
        'to': 'statements@freemail.example',
        'subject': 'Your October account statement',
        'attachments': ['statement_2026-10_acct-4471.pdf'],
        'body': 'Dear customer, please find your October statement attached.',
      },
      status: ApprovalStatus.held,
      riskScore: 0.64,
      tainted: false,
      userTask: 'Send customer #48213 their October statement',
      reasons: const [
        ApprovalReasonModel(
          layer: ReasonLayer.policy,
          message:
              "Statements may only go to a customer's verified email. "
              'statements@freemail.example is not on file for customer '
              '#48213.',
        ),
        ApprovalReasonModel(
          layer: ReasonLayer.keywords,
          message: 'The attachment contains an account number and balance.',
        ),
      ],
      createdAt: statementHeldAt,
      expiresAt: statementHeldAt.add(approvalWindow),
    ),
  ];
}
