import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/tool_labels.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/risk_score_chip.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/presentation/activity_labels.dart';

/// One gateway decision, with a stripe in the decision's color.
class EventTile extends StatelessWidget {
  const EventTile({required this.event, super.key});

  final ActivityEvent event;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final colors = context.statusColors.forTone(event.decision.tone);
    final locale = Localizations.localeOf(context).toLanguageTag();
    final time = DateFormat.MMMd(
      locale,
    ).add_Hm().format(event.createdAt.toLocal());
    final muted = context.colors.onSurfaceVariant;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: BorderDirectional(
            start: BorderSide(
              color: colors.foreground,
              width: AppSizes.accentStripe,
            ),
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(event.decision.icon, color: colors.foreground),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            toolLabel(l10n, event.tool),
                            style: context.textStyles.titleSmall,
                          ),
                        ),
                        Text(
                          time,
                          style: context.textStyles.bodySmall?.copyWith(
                            color: muted,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xxs),
                    Text(event.summary, style: context.textStyles.bodyMedium),
                    const SizedBox(height: AppSpacing.sm),
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.xs,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        StatusBadge(
                          label: event.decision.label(l10n),
                          tone: event.decision.tone,
                        ),
                        RiskScoreChip(score: event.riskScore),
                        Text(
                          event.agentId,
                          style: context.textStyles.bodySmall?.copyWith(
                            color: muted,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
