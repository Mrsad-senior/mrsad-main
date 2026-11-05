import 'dart:async';

import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';

/// A list that follows the gateway's live stream.
///
/// It runs [fetch] as soon as it is listened to, again for every event
/// [isRelevant] accepts, and again when [live] comes back online (to catch
/// up on what it missed). While [live] is not online it polls every
/// [fallbackInterval] instead. Values pushed to [updates] (e.g. after a
/// manual refresh) are forwarded. Fetches never overlap: events arriving
/// during one lead to a single fetch afterwards. A failed fetch is emitted
/// as a stream error and the stream carries on.
Stream<T> liveRefreshStream<T>({
  required Future<T> Function() fetch,
  required LiveUpdates live,
  required bool Function(SseEvent event) isRelevant,
  required Duration fallbackInterval,
  Stream<T>? updates,
}) {
  late final StreamController<T> controller;
  final subscriptions = <StreamSubscription<Object?>>[];
  Timer? poller;
  var fetching = false;
  var again = false;

  Future<void> refresh() async {
    if (fetching) {
      again = true;
      return;
    }
    fetching = true;
    do {
      again = false;
      try {
        final value = await fetch();
        if (!controller.isClosed) controller.add(value);
      } catch (error, stackTrace) {
        if (!controller.isClosed) controller.addError(error, stackTrace);
      }
    } while (again && !controller.isClosed);
    fetching = false;
  }

  void pollUnlessOnline(LiveStatus status) {
    if (status == LiveStatus.online) {
      poller?.cancel();
      poller = null;
    } else {
      poller ??= Timer.periodic(fallbackInterval, (_) => unawaited(refresh()));
    }
  }

  controller = StreamController<T>(
    onListen: () {
      subscriptions
        ..add(live.events.where(isRelevant).listen((_) => unawaited(refresh())))
        ..add(
          live.statusChanges.listen((status) {
            if (status == LiveStatus.online) unawaited(refresh());
            pollUnlessOnline(status);
          }),
        );
      if (updates != null) subscriptions.add(updates.listen(controller.add));
      pollUnlessOnline(live.status);
      unawaited(refresh());
    },
    onCancel: () async {
      poller?.cancel();
      for (final subscription in subscriptions) {
        await subscription.cancel();
      }
      await controller.close();
    },
  );
  return controller.stream;
}
