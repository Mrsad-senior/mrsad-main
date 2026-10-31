import 'package:flutter/material.dart';
import 'package:mirsad/core/theme/mirsad_colors.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_radii.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';

/// What a status means, which decides its color.
enum StatusTone { positive, negative, warning, neutral }

/// A small pill with a label, colored by [tone].
class StatusBadge extends StatelessWidget {
  const StatusBadge({
    required this.label,
    required this.tone,
    this.icon,
    super.key,
  });

  final String label;
  final StatusTone tone;
  final IconData? icon;

  @override
  Widget build(BuildContext context) {
    final colors = context.statusColors.forTone(tone);
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.container,
        borderRadius: AppRadii.badge,
      ),
      child: Padding(
        padding: const EdgeInsetsDirectional.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xxs,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: AppSizes.iconXs, color: colors.onContainer),
              const SizedBox(width: AppSpacing.xs),
            ],
            Text(
              label,
              style: context.textStyles.labelMedium?.copyWith(
                color: colors.onContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

extension StatusTonePalette on MirsadColors {
  StatusColors forTone(StatusTone tone) {
    return switch (tone) {
      StatusTone.positive => allowed,
      StatusTone.negative => denied,
      StatusTone.warning => held,
      StatusTone.neutral => neutral,
    };
  }
}
