import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/risk_score_chip.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/presentation/approval_labels.dart';

/// Status, risk and where the request came from.
class ApprovalHeader extends StatelessWidget {
  const ApprovalHeader({required this.approval, super.key});

  final Approval approval;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final locale = Localizations.localeOf(context).toLanguageTag();
    final requestedAt = DateFormat.yMMMd(
      locale,
    ).add_jm().format(approval.createdAt.toLocal());
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            StatusBadge(
              label: approval.status.label(l10n),
              tone: approval.status.tone,
            ),
            RiskScoreChip(score: approval.riskScore),
            if (approval.tainted)
              StatusBadge(
                label: l10n.taintedInput,
                tone: StatusTone.warning,
                icon: Icons.warning_amber_rounded,
              ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        _MetaLine(label: l10n.agentLabel, value: approval.agentId),
        _MetaLine(label: l10n.sectorLabel, value: approval.sector.label(l10n)),
        _MetaLine(label: l10n.requestedAtLabel, value: requestedAt),
      ],
    );
  }
}

class _MetaLine extends StatelessWidget {
  const _MetaLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsetsDirectional.only(top: AppSpacing.xxs),
      child: Text.rich(
        TextSpan(
          children: [
            TextSpan(
              text: '$label: ',
              style: TextStyle(color: context.colors.onSurfaceVariant),
            ),
            TextSpan(text: value),
          ],
        ),
        style: context.textStyles.bodyMedium,
      ),
    );
  }
}
