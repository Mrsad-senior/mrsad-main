import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/widgets/error_state.dart';
import 'package:mirsad/core/widgets/loading_state.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/presentation/cubit/approval_details_cubit.dart';
import 'package:mirsad/features/approvals/presentation/widgets/approval_details_body.dart';
import 'package:mirsad/features/approvals/presentation/widgets/decision_bar.dart';

/// One held action, with Approve / Reject.
class ApprovalDetailsPage extends StatelessWidget {
  const ApprovalDetailsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<ApprovalDetailsCubit, ApprovalDetailsState>(
      listenWhen: (previous, current) =>
          previous.submission != current.submission,
      listener: _onSubmissionChanged,
      builder: (context, state) {
        final l10n = context.l10n;
        final cubit = context.read<ApprovalDetailsCubit>();
        final approval = state.approval;
        return Scaffold(
          appBar: AppBar(title: Text(l10n.approvalDetailsTitle)),
          body: switch (state.status) {
            ApprovalDetailsStatus.loading => const LoadingState(),
            ApprovalDetailsStatus.failure => ErrorState(
              message: state.loadFailure!.localizedMessage(l10n),
              onRetry: cubit.retry,
            ),
            ApprovalDetailsStatus.ready => ApprovalDetailsBody(
              approval: approval!,
            ),
          },
          bottomNavigationBar:
              approval != null && approval.status == ApprovalStatus.held
              ? DecisionBar(
                  approval: approval,
                  submitting: state.isSubmitting,
                  onDecide: (decision, note) =>
                      cubit.decide(decision, note: note),
                )
              : null,
        );
      },
    );
  }

  void _onSubmissionChanged(BuildContext context, ApprovalDetailsState state) {
    final l10n = context.l10n;
    final messenger = ScaffoldMessenger.of(context);
    switch (state.submission) {
      case DecisionSubmission.succeeded:
        final message = state.decision == ReviewDecision.approve
            ? l10n.approvedMessage
            : l10n.rejectedMessage;
        messenger.showSnackBar(SnackBar(content: Text(message)));
        Navigator.of(context).maybePop();
      case DecisionSubmission.failed:
        messenger.showSnackBar(
          SnackBar(content: Text(state.submitFailure!.localizedMessage(l10n))),
        );
      case DecisionSubmission.idle:
      case DecisionSubmission.submitting:
        break;
    }
  }
}
