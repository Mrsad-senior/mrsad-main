import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/router/app_shell_tab.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

void main() {
  test('admins see every tab', () {
    expect(AppShellTab.visibleFor(ReviewerRole.admin), AppShellTab.values);
  });

  test('approvers do not see Activity', () {
    expect(AppShellTab.visibleFor(ReviewerRole.approver), [
      AppShellTab.approvals,
      AppShellTab.audit,
    ]);
  });

  test('auditors do not see Approvals', () {
    expect(AppShellTab.visibleFor(ReviewerRole.auditor), [
      AppShellTab.activity,
      AppShellTab.audit,
    ]);
  });

  test('branches match the router order', () {
    expect(
      AppShellTab.values.map((tab) => tab.branch),
      List.generate(AppShellTab.values.length, (i) => i),
    );
  });
}
