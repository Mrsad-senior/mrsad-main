import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/network/live/live_updates.dart';

/// The live connection's status, for the Online / Reconnecting indicator.
class LiveStatusCubit extends Cubit<LiveStatus> {
  LiveStatusCubit(LiveUpdates live) : super(live.status) {
    _subscription = live.statusChanges.listen(emit);
  }

  late final StreamSubscription<LiveStatus> _subscription;

  @override
  Future<void> close() async {
    await _subscription.cancel();
    return super.close();
  }
}
