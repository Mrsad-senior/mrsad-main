import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/tool_labels.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/theme/tokens/app_typography.dart';
import 'package:mirsad/core/widgets/tool_icon.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/presentation/approval_labels.dart';

/// What the user asked for, set against what the agent is trying to do, so
/// a mismatch is easy to spot.
class TaskComparison extends StatelessWidget {
  const TaskComparison({required this.approval, super.key});

  final Approval approval;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final amount = approval.amount;
    final recipient = approval.recipient;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Side(
              icon: Icons.person_outline,
              title: l10n.userAskedTitle,
              child: Text(
                approval.userTask,
                style: context.textStyles.bodyLarge,
              ),
            ),
            const _Divider(),
            _Side(
              icon: Icons.smart_toy_outlined,
              title: l10n.agentWantsTitle,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        toolIcon(approval.tool),
                        size: AppSizes.iconSm,
                        color: context.colors.primary,
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Flexible(
                        child: Text(
                          toolLabel(l10n, approval.tool),
                          style: context.textStyles.titleMedium,
                        ),
                      ),
                    ],
                  ),
                  Text(approval.tool, style: AppTypography.code),
                  if (amount != null)
                    Text(
                      formatAmount(context, amount, approval.currency),
                      style: context.textStyles.headlineSmall,
                    ),
                  if (recipient != null)
                    Text(
                      l10n.recipient(recipient),
                      style: context.textStyles.bodyMedium,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Side extends StatelessWidget {
  const _Side({required this.icon, required this.title, required this.child});

  final IconData icon;
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final muted = context.colors.onSurfaceVariant;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, size: AppSizes.iconSm, color: muted),
            const SizedBox(width: AppSpacing.xs),
            Text(
              title,
              style: context.textStyles.labelLarge?.copyWith(color: muted),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        child,
      ],
    );
  }
}

class _Divider extends StatelessWidget {
  const _Divider();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
      child: Row(
        children: [
          const Expanded(child: Divider()),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
            child: Icon(
              Icons.south,
              size: AppSizes.iconSm,
              color: context.colors.outline,
            ),
          ),
          const Expanded(child: Divider()),
        ],
      ),
    );
  }
}
