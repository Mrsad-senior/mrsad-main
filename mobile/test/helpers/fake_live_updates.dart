import 'dart:async';

import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';

/// A [LiveUpdates] the test drives: [emit] sends an event, [setStatus]
/// changes the connection status.
class FakeLiveUpdates implements LiveUpdates {
  FakeLiveUpdates({this._status = LiveStatus.online});

  final StreamController<SseEvent> _events = StreamController.broadcast();
  final StreamController<LiveStatus> _statusChanges =
      StreamController.broadcast();
  LiveStatus _status;
  int starts = 0;
  int stops = 0;

  @override
  Stream<SseEvent> get events => _events.stream;

  @override
  LiveStatus get status => _status;

  @override
  Stream<LiveStatus> get statusChanges => _statusChanges.stream;

  void emit(String event, [String data = '{}']) =>
      _events.add(SseEvent(event, data));

  void setStatus(LiveStatus status) {
    _status = status;
    _statusChanges.add(status);
  }

  @override
  void start() => starts++;

  @override
  Future<void> stop() async => stops++;

  Future<void> close() async {
    await _events.close();
    await _statusChanges.close();
  }
}

/// Lets pending microtasks and zero-length timers run.
Future<void> settle() => Future<void>.delayed(Duration.zero);

/// Waits up to a second for [condition], for work such as a Dio request
/// that takes more than one event-loop turn.
Future<void> eventually(bool Function() condition) async {
  for (var i = 0; i < 200 && !condition(); i++) {
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
  if (!condition()) throw StateError('Condition not met in time');
}
