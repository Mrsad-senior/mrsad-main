import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

import '../../approval_fixtures.dart';

void main() {
  test('parses a gateway approval record', () {
    final approval = ApprovalModel.fromJson(approvalJson()).toEntity();

    expect(approval.id, 'apr_7f3c2a');
    expect(approval.sector, Sector.finance);
    expect(approval.status, ApprovalStatus.held);
    expect(approval.riskScore, 0.9);
    expect(approval.amount, 50000);
    expect(approval.recipient, 'SA******************1234');
    expect(approval.userTask, 'Process this supplier invoice');
    expect(approval.tainted, isTrue);
    expect(approval.createdAt, DateTime.utc(2026, 10, 29, 9, 41, 7, 250));
    expect(approval.expiresAt, DateTime.utc(2026, 10, 29, 9, 43, 7, 250));
  });

  test('shows only the reasons that objected to the call', () {
    final approval = ApprovalModel.fromJson(approvalJson()).toEntity();

    expect(approval.reasons.map((r) => r.layer), [
      ReasonLayer.llmJudge,
      ReasonLayer.taint,
    ]);
    expect(
      approval.reasons.last.message,
      'The IBAN only appears inside the invoice.',
    );
  });

  test('maps every gateway status', () {
    const expected = {
      'pending': ApprovalStatus.held,
      'approved': ApprovalStatus.approved,
      'denied': ApprovalStatus.rejected,
      'expired': ApprovalStatus.expired,
      'cancelled': ApprovalStatus.expired,
    };
    for (final MapEntry(:key, :value) in expected.entries) {
      expect(ApprovalModel.fromJson(approvalJson(status: key)).status, value);
    }
  });

  test('rejects an unknown status', () {
    expect(
      () => ApprovalModel.fromJson(approvalJson(status: 'held')),
      throwsA(isA<DataFormatException>()),
    );
  });

  test('maps gateway layers and codes onto the app layers', () {
    const expected = {
      ('policy', 'CONSTRAINT_VIOLATION'): ReasonLayer.policy,
      ('ratelimit', 'RATE_LIMIT'): ReasonLayer.policy,
      ('approval', 'APPROVAL_POLICY'): ReasonLayer.policy,
      ('taint', 'TAINT_AFTER_INJECTION'): ReasonLayer.taint,
      ('detector', 'SCAN_FAILED'): ReasonLayer.keywords,
      ('system', 'TASK_INTENT_MISMATCH'): ReasonLayer.intent,
      ('system', 'SEMANTIC_TASK_MISMATCH'): ReasonLayer.llmJudge,
      ('system', 'NEW_BENEFICIARY'): ReasonLayer.policy,
      ('system', 'INTERNAL_ERROR'): ReasonLayer.other,
      ('sandbox', 'ANYTHING'): ReasonLayer.other,
    };
    for (final MapEntry(key: (layer, code), :value) in expected.entries) {
      expect(reasonLayerFromWire(layer, code), value, reason: '$layer/$code');
    }
  });

  test('confidential data leaving is not untrusted input', () {
    final approval = ApprovalModel.fromJson(
      approvalJson(
        reasons: [
          reasonJson(layer: 'taint', code: 'TAINT_CONFIDENTIAL_TO_EXTERNAL'),
          reasonJson(
            layer: 'taint',
            code: 'TAINT_UNTRUSTED_DESTINATION',
            action: 'allow',
          ),
        ],
      ),
    ).toEntity();

    expect(approval.tainted, isFalse);
    expect(approval.reasons, hasLength(1));
  });

  test('derives the sector from the policy agent like the gateway', () {
    Sector sectorOf(String agentId) => ApprovalModel.fromJson(
      approvalJson(agentId: agentId),
    ).toEntity().sector;

    expect(sectorOf('healthcare-assistant'), Sector.healthcare);
    expect(sectorOf('email-crm-assistant'), Sector.general);
  });

  test('leaves the user task empty while the gateway does not send it', () {
    final approval = ApprovalModel.fromJson(
      approvalJson(originalTask: null),
    ).toEntity();
    expect(approval.userTask, isEmpty);
  });

  test('decision request sends approve as a flag and leaves out no note', () {
    expect(
      const DecisionRequestModel(decision: ReviewDecision.approve).toJson(),
      {'approve': true},
    );
    expect(
      const DecisionRequestModel(
        decision: ReviewDecision.reject,
        note: 'Unknown IBAN',
      ).toJson(),
      {'approve': false, 'note': 'Unknown IBAN'},
    );
  });
}
