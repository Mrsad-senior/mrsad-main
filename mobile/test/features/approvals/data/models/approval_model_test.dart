import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

import '../../approval_fixtures.dart';

void main() {
  test('parses the contract example', () {
    final approval = ApprovalModel.fromJson(approvalJson()).toEntity();

    expect(approval.id, 'apr_7f3c2a');
    expect(approval.sector, Sector.finance);
    expect(approval.status, ApprovalStatus.held);
    expect(approval.riskScore, 0.92);
    expect(approval.amount, 50000);
    expect(approval.reasons.map((r) => r.layer), [
      ReasonLayer.intent,
      ReasonLayer.llmJudge,
    ]);
    expect(approval.createdAt, DateTime.utc(2026, 10, 29, 9, 41, 7));
  });

  test('reads an unknown layer as "other" instead of failing', () {
    final approval = ApprovalModel.fromJson(
      approvalJson(layer: 'sandbox'),
    ).toEntity();
    expect(approval.reasons.first.layer, ReasonLayer.other);
  });

  test('rejects an unknown status', () {
    expect(
      () => ApprovalModel.fromJson(approvalJson(status: 'paused')),
      throwsA(isA<DataFormatException>()),
    );
  });

  test('writes back the same JSON keys', () {
    final json = ApprovalModel.fromJson(approvalJson()).toJson();
    expect(json['agent_id'], 'banking-assistant');
    expect(json['risk_score'], 0.92);
    expect((json['reasons'] as List).last, {
      'layer': 'llm_judge',
      'message': 'Looks like payment redirection.',
    });
  });

  test('decision request leaves out an empty note', () {
    expect(
      const DecisionRequestModel(decision: ReviewDecision.approve).toJson(),
      {'decision': 'approve'},
    );
    expect(
      const DecisionRequestModel(
        decision: ReviewDecision.reject,
        note: 'Unknown IBAN',
      ).toJson(),
      {'decision': 'reject', 'note': 'Unknown IBAN'},
    );
  });
}
