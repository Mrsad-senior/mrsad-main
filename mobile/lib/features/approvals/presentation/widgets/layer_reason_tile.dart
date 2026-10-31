import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_reason.dart';
import 'package:mirsad/features/approvals/presentation/approval_labels.dart';

/// One Mirsad layer's reason for holding the action.
class LayerReasonTile extends StatelessWidget {
  const LayerReasonTile({required this.reason, super.key});

  final ApprovalReason reason;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          reason.layer.icon,
          size: AppSizes.iconMd,
          color: context.statusColors.held.foreground,
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                reason.layer.label(context.l10n),
                style: context.textStyles.titleSmall,
              ),
              const SizedBox(height: AppSpacing.xxs),
              Text(reason.message, style: context.textStyles.bodyMedium),
            ],
          ),
        ),
      ],
    );
  }
}
