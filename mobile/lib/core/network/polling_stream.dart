import 'dart:async';

/// A stream for sources without push updates, such as the gateway API.
///
/// It runs [fetch] as soon as it is listened to and then every [interval],
/// and forwards every value pushed to [updates] (e.g. after a manual refresh).
/// A failed fetch is emitted as a stream error and polling carries on.
Stream<T> pollingStream<T>({
  required Future<T> Function() fetch,
  required Duration interval,
  Stream<T>? updates,
}) {
  late final StreamController<T> controller;
  Timer? timer;
  StreamSubscription<T>? updatesSubscription;

  Future<void> poll() async {
    try {
      final value = await fetch();
      if (!controller.isClosed) controller.add(value);
    } catch (error, stackTrace) {
      if (!controller.isClosed) controller.addError(error, stackTrace);
    }
  }

  controller = StreamController<T>(
    onListen: () {
      updatesSubscription = updates?.listen(controller.add);
      timer = Timer.periodic(interval, (_) => unawaited(poll()));
      unawaited(poll());
    },
    onCancel: () async {
      timer?.cancel();
      await updatesSubscription?.cancel();
      await controller.close();
    },
  );
  return controller.stream;
}
