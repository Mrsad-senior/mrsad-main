import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/approvals/presentation/approval_labels.dart';
import 'package:mirsad/features/approvals/presentation/widgets/expiry_ticker.dart';

/// A live "Auto-rejects in 4:07" label.
class ExpiryCountdown extends StatelessWidget {
  const ExpiryCountdown({required this.expiresAt, super.key});

  final DateTime expiresAt;

  @override
  Widget build(BuildContext context) {
    return ExpiryTicker(
      expiresAt: expiresAt,
      builder: (context, remaining) => ExpiryLabel(remaining: remaining),
    );
  }
}

/// "Auto-rejects in 4:07", red in the last minute, or an "Expired" badge.
class ExpiryLabel extends StatelessWidget {
  const ExpiryLabel({required this.remaining, super.key});

  static const urgentBelow = Duration(minutes: 1);

  final Duration remaining;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    if (remaining == Duration.zero) {
      return StatusBadge(
        label: l10n.statusExpired,
        tone: StatusTone.neutral,
        icon: Icons.timer_off_outlined,
      );
    }
    final status = context.statusColors;
    final color = remaining < urgentBelow
        ? status.denied.foreground
        : status.held.foreground;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.timer_outlined, size: AppSizes.iconSm, color: color),
        const SizedBox(width: AppSpacing.xs),
        Text(
          l10n.expiresIn(formatCountdown(remaining)),
          style: context.textStyles.labelLarge?.copyWith(
            color: color,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
      ],
    );
  }
}
