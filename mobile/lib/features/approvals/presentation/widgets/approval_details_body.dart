import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/section_card.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/presentation/widgets/approval_header.dart';
import 'package:mirsad/features/approvals/presentation/widgets/arguments_table.dart';
import 'package:mirsad/features/approvals/presentation/widgets/layer_reason_tile.dart';
import 'package:mirsad/features/approvals/presentation/widgets/task_comparison.dart';

/// Everything a reviewer needs to decide on [approval].
class ApprovalDetailsBody extends StatelessWidget {
  const ApprovalDetailsBody({required this.approval, super.key});

  final Approval approval;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        ApprovalHeader(approval: approval),
        const SizedBox(height: AppSpacing.lg),
        TaskComparison(approval: approval),
        const SizedBox(height: AppSpacing.lg),
        SectionCard(
          title: l10n.reasonsTitle,
          child: Column(
            children: [
              for (final (index, reason) in approval.reasons.indexed) ...[
                if (index > 0) const SizedBox(height: AppSpacing.md),
                LayerReasonTile(reason: reason),
              ],
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        SectionCard(
          title: l10n.argumentsTitle,
          child: ArgumentsTable(arguments: approval.arguments),
        ),
      ],
    );
  }
}
