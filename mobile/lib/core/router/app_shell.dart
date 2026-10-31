import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/widgets/language_toggle_button.dart';
import 'package:mirsad/features/auth/presentation/widgets/sign_out_button.dart';

/// The signed-in layout: an app bar and the Approvals / Activity / Audit
/// bottom navigation around the current tab.
class AppShell extends StatelessWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final index = navigationShell.currentIndex;
    final titles = [l10n.approvalsTitle, l10n.activityTitle, l10n.auditTitle];
    return Scaffold(
      appBar: AppBar(
        title: Text(titles[index]),
        actions: const [LanguageToggleButton(), SignOutButton()],
      ),
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (selected) => navigationShell.goBranch(
          selected,
          initialLocation: selected == index,
        ),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.pending_actions_outlined),
            selectedIcon: const Icon(Icons.pending_actions),
            label: l10n.navApprovals,
          ),
          NavigationDestination(
            icon: const Icon(Icons.timeline_outlined),
            selectedIcon: const Icon(Icons.timeline),
            label: l10n.navActivity,
          ),
          NavigationDestination(
            icon: const Icon(Icons.verified_user_outlined),
            selectedIcon: const Icon(Icons.verified_user),
            label: l10n.navAudit,
          ),
        ],
      ),
    );
  }
}
