import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/domain/usecases/decide_approval.dart';

/// The reviewer confirmed the decision, with an optional note.
class DecisionConfirmation {
  const DecisionConfirmation({this.note});

  final String? note;
}

/// Asks the reviewer to confirm [decision]. Returns null if they cancel.
Future<DecisionConfirmation?> showDecisionDialog(
  BuildContext context, {
  required ReviewDecision decision,
  required String toolName,
}) {
  return showDialog<DecisionConfirmation>(
    context: context,
    builder: (_) => DecisionDialog(decision: decision, toolName: toolName),
  );
}

class DecisionDialog extends StatefulWidget {
  const DecisionDialog({
    required this.decision,
    required this.toolName,
    super.key,
  });

  static const noteFieldKey = Key('decision-dialog-note');
  static const confirmKey = Key('decision-dialog-confirm');

  final ReviewDecision decision;
  final String toolName;

  @override
  State<DecisionDialog> createState() => _DecisionDialogState();
}

class _DecisionDialogState extends State<DecisionDialog> {
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final rejecting = widget.decision == ReviewDecision.reject;
    final denied = context.statusColors.denied;
    return AlertDialog(
      title: Text(
        rejecting ? l10n.confirmRejectTitle : l10n.confirmApproveTitle,
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            rejecting
                ? l10n.confirmRejectBody(widget.toolName)
                : l10n.confirmApproveBody(widget.toolName),
          ),
          const SizedBox(height: AppSpacing.lg),
          TextField(
            key: DecisionDialog.noteFieldKey,
            controller: _note,
            minLines: 1,
            maxLines: 3,
            maxLength: DecideApproval.maxNoteLength,
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              labelText: l10n.noteLabel,
              hintText: l10n.noteHint,
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: Text(l10n.cancel),
        ),
        FilledButton(
          key: DecisionDialog.confirmKey,
          style: rejecting
              ? FilledButton.styleFrom(
                  backgroundColor: denied.foreground,
                  foregroundColor: context.colors.onError,
                )
              : null,
          onPressed: () =>
              Navigator.of(context).pop(DecisionConfirmation(note: _note.text)),
          child: Text(rejecting ? l10n.reject : l10n.approve),
        ),
      ],
    );
  }
}
