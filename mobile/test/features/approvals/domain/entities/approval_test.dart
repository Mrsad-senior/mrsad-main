import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';

import '../../../../helpers/fake_clock.dart';
import '../../approval_fixtures.dart';

void main() {
  test('reads the amount, currency and recipient from the arguments', () {
    final approval = transferApproval();
    expect(approval.amount, 50000);
    expect(approval.currency, 'SAR');
    expect(approval.recipient, 'SA4420000001234567891234');
  });

  test('is open while held and before it expires', () {
    final approval = transferApproval();
    expect(approval.isOpenAt(testNow), isTrue);
    expect(approval.isOpenAt(approval.expiresAt), isFalse);
    expect(
      transferApproval(status: ApprovalStatus.rejected).isOpenAt(testNow),
      isFalse,
    );
  });

  test('time left never goes below zero', () {
    final approval = transferApproval();
    expect(
      approval.timeLeftAt(testNow),
      const Duration(minutes: 4, seconds: 20),
    );
    expect(
      approval.timeLeftAt(approval.expiresAt.add(const Duration(hours: 1))),
      Duration.zero,
    );
  });
}
