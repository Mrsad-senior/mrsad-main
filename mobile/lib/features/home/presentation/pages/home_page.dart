import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/error_state.dart';
import 'package:mirsad/core/widgets/fill_scroll_view.dart';
import 'package:mirsad/core/widgets/loading_state.dart';
import 'package:mirsad/features/home/presentation/cubit/home_cubit.dart';
import 'package:mirsad/features/home/presentation/widgets/home_shortcuts.dart';
import 'package:mirsad/features/home/presentation/widgets/overview_section.dart';

/// The first tab: the gateway's last 24 hours, then shortcuts to the
/// detector playground and the demo chat.
class HomePage extends StatelessWidget {
  const HomePage({required this.showDetector, super.key});

  /// Whether the reviewer's role may use the detector playground.
  final bool showDetector;

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<HomeCubit, HomeState>(
      listenWhen: (previous, current) =>
          current.status == HomeStatus.ready &&
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
        final cubit = context.read<HomeCubit>();
        final shortcuts = HomeShortcuts(showDetector: showDetector);
        final Widget content = switch (state.status) {
          HomeStatus.loading => const LoadingState(),
          HomeStatus.failure => FillScrollView(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                ErrorState(
                  message: state.failure!.localizedMessage(context.l10n),
                  onRetry: cubit.retry,
                ),
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: shortcuts,
                ),
              ],
            ),
          ),
          HomeStatus.ready => ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(AppSpacing.lg),
            children: [
              OverviewSection(stats: state.stats!),
              const SizedBox(height: AppSpacing.xl),
              shortcuts,
            ],
          ),
        };
        if (state.status == HomeStatus.loading) return content;
        return RefreshIndicator(onRefresh: cubit.refresh, child: content);
      },
    );
  }
}
