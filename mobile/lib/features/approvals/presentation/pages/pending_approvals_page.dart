import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/empty_state.dart';
import 'package:mirsad/core/widgets/error_state.dart';
import 'package:mirsad/core/widgets/fill_scroll_view.dart';
import 'package:mirsad/core/widgets/loading_state.dart';
import 'package:mirsad/features/approvals/presentation/cubit/pending_approvals_cubit.dart';
import 'package:mirsad/features/approvals/presentation/widgets/approval_tile.dart';

/// The held actions waiting for this reviewer.
class PendingApprovalsPage extends StatelessWidget {
  const PendingApprovalsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<PendingApprovalsCubit, PendingApprovalsState>(
      listenWhen: (previous, current) =>
          current.status == PendingApprovalsStatus.ready &&
          current.failure != null &&
          current.failure != previous.failure,
      listener: (context, state) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(state.failure!.localizedMessage(context.l10n)),
          ),
        );
      },
      builder: (context, state) {
        final l10n = context.l10n;
        final cubit = context.read<PendingApprovalsCubit>();
        final content = switch (state.status) {
          PendingApprovalsStatus.loading => null,
          PendingApprovalsStatus.failure => FillScrollView(
            child: ErrorState(
              message: state.failure!.localizedMessage(l10n),
              onRetry: cubit.retry,
            ),
          ),
          PendingApprovalsStatus.ready when state.approvals.isEmpty =>
            FillScrollView(
              child: EmptyState(
                icon: Icons.verified_outlined,
                title: l10n.pendingEmptyTitle,
                message: l10n.pendingEmptyMessage,
              ),
            ),
          PendingApprovalsStatus.ready => ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(AppSpacing.lg),
            itemCount: state.approvals.length,
            separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.md),
            itemBuilder: (context, index) {
              final approval = state.approvals[index];
              return ApprovalTile(
                approval: approval,
                onTap: () =>
                    context.push(AppRoutes.approvalDetails(approval.id)),
              );
            },
          ),
        };
        if (content == null) return const LoadingState();
        return RefreshIndicator(onRefresh: cubit.refresh, child: content);
      },
    );
  }
}
