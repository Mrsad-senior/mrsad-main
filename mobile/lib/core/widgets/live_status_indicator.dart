import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/network/live/live_status_cubit.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/widgets/status_badge.dart';

/// "Online" while the gateway's live stream is up, "Reconnecting" while the
/// app retries (lists poll meanwhile), nothing while signed out. Reads
/// [LiveStatusCubit] from context.
class LiveStatusIndicator extends StatelessWidget {
  const LiveStatusIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final status = context.watch<LiveStatusCubit>().state;
    return switch (status) {
      LiveStatus.offline => const SizedBox.shrink(),
      LiveStatus.online => StatusBadge(
        label: l10n.liveOnline,
        tone: StatusTone.positive,
        icon: Icons.wifi,
      ),
      LiveStatus.connecting || LiveStatus.reconnecting => StatusBadge(
        label: l10n.liveReconnecting,
        tone: StatusTone.warning,
        icon: Icons.sync,
      ),
    };
  }
}
