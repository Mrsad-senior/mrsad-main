import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

/// One bottom-navigation tab. [branch] is its index in the router's
/// `StatefulShellRoute`, which keeps every branch even when a tab is hidden.
enum AppShellTab {
  home(
    branch: 0,
    icon: Icons.dashboard_outlined,
    selectedIcon: Icons.dashboard,
  ),
  approvals(
    branch: 1,
    icon: Icons.pending_actions_outlined,
    selectedIcon: Icons.pending_actions,
  ),
  activity(
    branch: 2,
    icon: Icons.timeline_outlined,
    selectedIcon: Icons.timeline,
  ),
  audit(
    branch: 3,
    icon: Icons.verified_user_outlined,
    selectedIcon: Icons.verified_user,
  ),
  account(branch: 4, icon: Icons.person_outline, selectedIcon: Icons.person);

  const AppShellTab({
    required this.branch,
    required this.icon,
    required this.selectedIcon,
  });

  final int branch;
  final IconData icon;
  final IconData selectedIcon;

  /// Whether [role] sees this tab. Without a role (the moment before the
  /// sign-in redirect) only tabs every role may use are shown.
  bool isVisibleFor(ReviewerRole? role) => switch (this) {
    home => true,
    approvals => role?.canReviewApprovals ?? false,
    activity => role?.canReadAudit ?? false,
    audit || account => true,
  };

  String label(AppLocalizations l10n) => switch (this) {
    home => l10n.navHome,
    approvals => l10n.navApprovals,
    activity => l10n.navActivity,
    audit => l10n.navAudit,
    account => l10n.navAccount,
  };

  String title(AppLocalizations l10n) => switch (this) {
    home => l10n.homeTitle,
    approvals => l10n.approvalsTitle,
    activity => l10n.activityTitle,
    audit => l10n.auditTitle,
    account => l10n.accountTitle,
  };

  static List<AppShellTab> visibleFor(ReviewerRole? role) => [
    for (final tab in values)
      if (tab.isVisibleFor(role)) tab,
  ];
}
