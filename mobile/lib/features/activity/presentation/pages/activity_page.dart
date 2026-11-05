import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/empty_state.dart';
import 'package:mirsad/core/widgets/error_state.dart';
import 'package:mirsad/core/widgets/fill_scroll_view.dart';
import 'package:mirsad/core/widgets/loading_state.dart';
import 'package:mirsad/features/activity/presentation/cubit/activity_cubit.dart';
import 'package:mirsad/features/activity/presentation/widgets/decision_filter_bar.dart';
import 'package:mirsad/features/activity/presentation/widgets/event_tile.dart';

/// Every action the agents tried, color-coded by the gateway's decision.
class ActivityPage extends StatelessWidget {
  const ActivityPage({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<ActivityCubit, ActivityState>(
      listenWhen: (previous, current) =>
          current.status == ActivityStatus.ready &&
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
        final cubit = context.read<ActivityCubit>();
        return switch (state.status) {
          ActivityStatus.loading => const LoadingState(),
          ActivityStatus.failure => RefreshIndicator(
            onRefresh: cubit.refresh,
            child: FillScrollView(
              child: ErrorState(
                message: state.failure!.localizedMessage(context.l10n),
                onRetry: cubit.retry,
              ),
            ),
          ),
          ActivityStatus.ready => Column(
            children: [
              DecisionFilterBar(
                selected: state.filter,
                total: state.events.length,
                countOf: state.countOf,
                onSelected: cubit.setFilter,
              ),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: cubit.refresh,
                  child: _Feed(state: state),
                ),
              ),
            ],
          ),
        };
      },
    );
  }
}

class _Feed extends StatelessWidget {
  const _Feed({required this.state});

  final ActivityState state;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final events = state.visibleEvents;
    if (events.isEmpty) {
      final nothingYet = state.events.isEmpty;
      return FillScrollView(
        child: EmptyState(
          icon: nothingYet ? Icons.timeline : Icons.filter_alt_off_outlined,
          title: nothingYet
              ? l10n.activityEmptyTitle
              : l10n.activityFilteredEmpty,
          message: nothingYet ? l10n.activityEmptyMessage : null,
        ),
      );
    }
    return ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsetsDirectional.fromSTEB(
        AppSpacing.lg,
        0,
        AppSpacing.lg,
        AppSpacing.lg,
      ),
      itemCount: events.length,
      separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.md),
      itemBuilder: (context, index) => EventTile(event: events[index]),
    );
  }
}
