import 'package:flutter/material.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/status_badge.dart';

/// A big number with a label under it, colored by [tone].
class StatTile extends StatelessWidget {
  const StatTile({
    required this.label,
    required this.value,
    this.tone = StatusTone.neutral,
    super.key,
  });

  final String label;
  final String value;
  final StatusTone tone;

  @override
  Widget build(BuildContext context) {
    final color = tone == StatusTone.neutral
        ? context.colors.onSurface
        : context.statusColors.forTone(tone).foreground;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: context.textStyles.headlineSmall?.copyWith(color: color),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              label,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: context.textStyles.bodySmall?.copyWith(
                color: context.colors.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
