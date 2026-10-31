import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';
import 'package:mirsad/features/activity/presentation/activity_labels.dart';

/// Chips to show all events, or only allowed, denied or held ones.
class DecisionFilterBar extends StatelessWidget {
  const DecisionFilterBar({
    required this.selected,
    required this.total,
    required this.countOf,
    required this.onSelected,
    super.key,
  });

  final GatewayDecision? selected;
  final int total;
  final int Function(GatewayDecision decision) countOf;
  final ValueChanged<GatewayDecision?> onSelected;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsetsDirectional.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        children: [
          ChoiceChip(
            label: Text('${l10n.filterAll} ($total)'),
            selected: selected == null,
            onSelected: (_) => onSelected(null),
          ),
          for (final decision in GatewayDecision.values) ...[
            const SizedBox(width: AppSpacing.sm),
            ChoiceChip(
              avatar: Icon(
                decision.icon,
                size: AppSizes.iconSm,
                color: context.statusColors.forTone(decision.tone).foreground,
              ),
              label: Text('${decision.label(l10n)} (${countOf(decision)})'),
              selected: selected == decision,
              onSelected: (_) => onSelected(decision),
            ),
          ],
        ],
      ),
    );
  }
}
