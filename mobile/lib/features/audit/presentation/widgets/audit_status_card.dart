import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/mirsad_colors.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_radii.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/features/audit/domain/entities/audit_chain_status.dart';

/// A large intact / broken verdict for the audit chain.
class AuditStatusCard extends StatelessWidget {
  const AuditStatusCard({required this.status, super.key});

  final AuditChainStatus status;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final StatusColors colors;
    final IconData icon;
    final String title;
    final String message;
    if (status.valid) {
      colors = context.statusColors.allowed;
      icon = Icons.verified_user;
      title = l10n.auditValidTitle;
      message = l10n.auditValidMessage;
    } else {
      final brokenAt = status.brokenAt;
      colors = context.statusColors.denied;
      icon = Icons.gpp_bad;
      title = l10n.auditBrokenTitle;
      message = brokenAt == null
          ? l10n.auditBrokenUnknownEntry
          : l10n.auditBrokenMessage(brokenAt);
    }
    return DecoratedBox(
      decoration: BoxDecoration(
        color: colors.container,
        borderRadius: AppRadii.card,
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          children: [
            Icon(icon, size: AppSizes.iconXl, color: colors.foreground),
            const SizedBox(height: AppSpacing.md),
            Text(
              title,
              textAlign: TextAlign.center,
              style: context.textStyles.titleLarge?.copyWith(
                color: colors.onContainer,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              textAlign: TextAlign.center,
              style: context.textStyles.bodyLarge?.copyWith(
                color: colors.onContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
