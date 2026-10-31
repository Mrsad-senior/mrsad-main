import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/error_state.dart';
import 'package:mirsad/core/widgets/loading_state.dart';
import 'package:mirsad/features/audit/presentation/cubit/audit_cubit.dart';
import 'package:mirsad/features/audit/presentation/widgets/audit_status_card.dart';

/// Whether the audit log's hash chain is intact.
class AuditPage extends StatelessWidget {
  const AuditPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<AuditCubit, AuditState>(
      listenWhen: (previous, current) =>
          current.status == AuditStatus.ready &&
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
        final cubit = context.read<AuditCubit>();
        return switch (state.status) {
          AuditStatus.loading => const LoadingState(),
          AuditStatus.failure => ErrorState(
            message: state.failure!.localizedMessage(l10n),
            onRetry: cubit.verify,
          ),
          AuditStatus.ready => Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: ConstrainedBox(
                constraints: const BoxConstraints(
                  maxWidth: AppSizes.maxContentWidth,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    AuditStatusCard(status: state.result!),
                    const SizedBox(height: AppSpacing.xl),
                    FilledButton.tonalIcon(
                      onPressed: state.verifying ? null : cubit.verify,
                      icon: state.verifying
                          ? const SizedBox.square(
                              dimension: AppSizes.iconSm,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.refresh),
                      label: Text(l10n.auditVerifyAgain),
                    ),
                  ],
                ),
              ),
            ),
          ),
        };
      },
    );
  }
}
