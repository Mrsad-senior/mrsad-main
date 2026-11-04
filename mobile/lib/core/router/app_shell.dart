import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/router/app_shell_tab.dart';
import 'package:mirsad/core/widgets/language_toggle_button.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:mirsad/features/auth/presentation/widgets/sign_out_button.dart';

/// The signed-in layout: an app bar and the bottom navigation around the
/// current tab. Tabs the reviewer's role cannot use are left out.
class AppShell extends StatelessWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final role = context.select<AuthCubit, ReviewerRole?>(
      (cubit) => cubit.state.reviewer?.role,
    );
    final tabs = AppShellTab.visibleFor(role);
    final current = navigationShell.currentIndex;
    // The redirect keeps reviewers off hidden tabs; fall back to the first
    // one for the frame before it runs.
    final selected = tabs.indexWhere((tab) => tab.branch == current);
    final tab = tabs[selected < 0 ? 0 : selected];
    return Scaffold(
      appBar: AppBar(
        title: Text(tab.title(l10n)),
        actions: const [LanguageToggleButton(), SignOutButton()],
      ),
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: selected < 0 ? 0 : selected,
        onDestinationSelected: (index) {
          final branch = tabs[index].branch;
          navigationShell.goBranch(branch, initialLocation: branch == current);
        },
        destinations: [
          for (final tab in tabs)
            NavigationDestination(
              icon: Icon(tab.icon),
              selectedIcon: Icon(tab.selectedIcon),
              label: tab.label(l10n),
            ),
        ],
      ),
    );
  }
}
