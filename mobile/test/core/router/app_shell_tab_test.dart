import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/router/app_shell_tab.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

void main() {
  test('admins see every tab', () {
    expect(AppShellTab.visibleFor(ReviewerRole.admin), AppShellTab.values);
  });

  test('approvers do not see Activity', () {
    expect(AppShellTab.visibleFor(ReviewerRole.approver), [
      AppShellTab.home,
      AppShellTab.approvals,
      AppShellTab.audit,
      AppShellTab.account,
    ]);
  });

  test('auditors do not see Approvals', () {
    expect(AppShellTab.visibleFor(ReviewerRole.auditor), [
      AppShellTab.home,
      AppShellTab.activity,
      AppShellTab.audit,
      AppShellTab.account,
    ]);
  });

  test('branches match the router order', () {
    expect(
      AppShellTab.values.map((tab) => tab.branch),
      List.generate(AppShellTab.values.length, (i) => i),
    );
  });
}
