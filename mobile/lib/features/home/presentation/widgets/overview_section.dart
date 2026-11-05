import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/tool_labels.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/section_card.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/core/widgets/tool_icon.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/presentation/widgets/stat_tile.dart';

/// The overview's figures: decision counts, the audit chain, decision time
/// and the busiest tools.
class OverviewSection extends StatelessWidget {
  const OverviewSection({required this.stats, super.key});

  final OverviewStats stats;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final locale = Localizations.localeOf(context).toLanguageTag();
    final number = NumberFormat.decimalPattern(locale);
    final decimal = NumberFormat('0.0', locale);
    String count(int value) => number.format(value);
    final median = stats.medianLatencyMs;
    final p95 = stats.p95LatencyMs;
    final tools = stats.busiestTools();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          l10n.homeWindow(number.format(stats.windowHours.round())),
          style: context.textStyles.titleMedium,
        ),
        const SizedBox(height: AppSpacing.md),
        _TwoColumns(
          children: [
            StatTile(label: l10n.homeCalls, value: count(stats.totalCalls)),
            StatTile(
              label: l10n.homeAllowed,
              value: count(stats.allowed),
              tone: StatusTone.positive,
            ),
            StatTile(
              label: l10n.homeDenied,
              value: count(stats.denied),
              tone: StatusTone.negative,
            ),
            StatTile(
              label: l10n.homeHeld,
              value: count(stats.heldForReview),
              tone: StatusTone.warning,
            ),
            StatTile(
              label: l10n.homeWaiting,
              value: count(stats.waitingNow),
              tone: StatusTone.warning,
            ),
            StatTile(
              label: l10n.homeInjections,
              value: count(stats.injectionsDetected),
              tone: StatusTone.negative,
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.lg),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            switch (stats.auditOk) {
              true => StatusBadge(
                label: l10n.homeAuditOk,
                tone: StatusTone.positive,
                icon: Icons.verified_user,
              ),
              false => StatusBadge(
                label: l10n.homeAuditBroken,
                tone: StatusTone.negative,
                icon: Icons.gpp_bad,
              ),
              null => StatusBadge(
                label: l10n.homeAuditUnknown,
                tone: StatusTone.neutral,
                icon: Icons.help_outline,
              ),
            },
            if (median != null && p95 != null)
              StatusBadge(
                label: l10n.homeLatency(
                  decimal.format(median),
                  decimal.format(p95),
                ),
                tone: StatusTone.neutral,
                icon: Icons.speed,
              ),
          ],
        ),
        if (tools.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.lg),
          SectionCard(
            title: l10n.homeBusiestTools,
            child: Column(
              children: [
                for (final tool in tools)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(toolIcon(tool.tool)),
                    title: Text(toolLabel(l10n, tool.tool)),
                    trailing: Text(
                      count(tool.total),
                      style: context.textStyles.titleMedium,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

/// Lays [children] out two to a row.
class _TwoColumns extends StatelessWidget {
  const _TwoColumns({required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = (constraints.maxWidth - AppSpacing.md) / 2;
        return Wrap(
          spacing: AppSpacing.md,
          runSpacing: AppSpacing.md,
          children: [
            for (final child in children) SizedBox(width: width, child: child),
          ],
        );
      },
    );
  }
}
