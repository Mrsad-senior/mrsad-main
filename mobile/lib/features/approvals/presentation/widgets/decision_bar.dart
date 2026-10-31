import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/tool_labels.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/presentation/widgets/decision_dialog.dart';
import 'package:mirsad/features/approvals/presentation/widgets/expiry_countdown.dart';
import 'package:mirsad/features/approvals/presentation/widgets/expiry_ticker.dart';

/// Approve / Reject buttons with the auto-reject countdown. The buttons
/// turn off while a decision is being sent and once the time runs out.
class DecisionBar extends StatelessWidget {
  const DecisionBar({
    required this.approval,
    required this.submitting,
    required this.onDecide,
    super.key,
  });

  static const rejectKey = Key('decision-bar-reject');
  static const approveKey = Key('decision-bar-approve');

  final Approval approval;
  final bool submitting;
  final void Function(ReviewDecision decision, String? note) onDecide;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final allowed = context.statusColors.allowed;
    final denied = context.statusColors.denied;
    return Material(
      color: context.colors.surfaceContainer,
      child: SafeArea(
        top: false,
        child: ExpiryTicker(
          expiresAt: approval.expiresAt,
          builder: (context, remaining) {
            final enabled = !submitting && remaining > Duration.zero;
            return Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (submitting)
                    const LinearProgressIndicator()
                  else
                    ExpiryLabel(remaining: remaining),
                  const SizedBox(height: AppSpacing.md),
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton.icon(
                          key: rejectKey,
                          style: FilledButton.styleFrom(
                            backgroundColor: denied.foreground,
                            foregroundColor: context.colors.onError,
                          ),
                          onPressed: enabled
                              ? () => _confirm(context, ReviewDecision.reject)
                              : null,
                          icon: const Icon(Icons.block),
                          label: Text(l10n.reject),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: OutlinedButton.icon(
                          key: approveKey,
                          style: OutlinedButton.styleFrom(
                            foregroundColor: allowed.foreground,
                          ),
                          onPressed: enabled
                              ? () => _confirm(context, ReviewDecision.approve)
                              : null,
                          icon: const Icon(Icons.check),
                          label: Text(l10n.approve),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }

  Future<void> _confirm(BuildContext context, ReviewDecision decision) async {
    final confirmation = await showDecisionDialog(
      context,
      decision: decision,
      toolName: toolLabel(context.l10n, approval.tool),
    );
    if (confirmation != null) onDecide(decision, confirmation.note);
  }
}
