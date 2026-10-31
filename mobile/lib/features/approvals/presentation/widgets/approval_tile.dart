import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/tool_labels.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/risk_score_chip.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/core/widgets/tool_icon.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/presentation/approval_labels.dart';
import 'package:mirsad/features/approvals/presentation/widgets/expiry_countdown.dart';

/// One held action in the pending list.
class ApprovalTile extends StatelessWidget {
  const ApprovalTile({required this.approval, required this.onTap, super.key});

  final Approval approval;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final amount = approval.amount;
    final recipient = approval.recipient;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(toolIcon(approval.tool), color: context.colors.primary),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      toolLabel(l10n, approval.tool),
                      style: context.textStyles.titleMedium,
                    ),
                  ),
                  RiskScoreChip(score: approval.riskScore),
                ],
              ),
              if (amount != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  formatAmount(context, amount, approval.currency),
                  style: context.textStyles.headlineSmall,
                ),
              ],
              if (recipient != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  l10n.recipient(recipient),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: context.textStyles.bodyMedium?.copyWith(
                    color: context.colors.onSurfaceVariant,
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              Row(
                children: [
                  if (approval.tainted)
                    StatusBadge(
                      label: l10n.taintedInput,
                      tone: StatusTone.warning,
                      icon: Icons.warning_amber_rounded,
                    ),
                  const Spacer(),
                  ExpiryCountdown(expiresAt: approval.expiresAt),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
