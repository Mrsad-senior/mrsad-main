import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/core/widgets/section_card.dart';

/// Links to the detector playground (for roles that may use it) and the
/// demo chat.
class HomeShortcuts extends StatelessWidget {
  const HomeShortcuts({required this.showDetector, super.key});

  final bool showDetector;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return SectionCard(
      title: l10n.homeToolsTitle,
      child: Column(
        children: [
          if (showDetector)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.manage_search),
              title: Text(l10n.detectorTitle),
              subtitle: Text(l10n.homeDetectorSubtitle),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push(AppRoutes.detector),
            ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.chat_bubble_outline),
            title: Text(l10n.chatTitle),
            subtitle: Text(l10n.homeChatSubtitle),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => context.push(AppRoutes.chat),
          ),
        ],
      ),
    );
  }
}
