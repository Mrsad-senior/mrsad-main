import 'package:mirsad/core/network/live/sse_event.dart';

/// The state of the live connection to the gateway.
enum LiveStatus {
  /// Not connected and not trying, e.g. while signed out.
  offline,

  /// The first attempt after [LiveUpdates.start].
  connecting,

  /// Subscribed: the gateway sent `ready`.
  online,

  /// The connection dropped or was refused; retrying with backoff. Lists
  /// poll in the meantime.
  reconnecting,
}

/// Push updates from the gateway. The API implementation reads
/// `GET /api/stream`; data sources refetch when a relevant event arrives and
/// poll while [status] is not [LiveStatus.online].
abstract interface class LiveUpdates {
  /// Events while connected. A broadcast stream that never errors.
  Stream<SseEvent> get events;

  LiveStatus get status;

  /// Emits every change of [status].
  Stream<LiveStatus> get statusChanges;

  /// Connects and keeps reconnecting until [stop]. Does nothing if already
  /// started.
  void start();

  /// Closes the connection and stops retrying.
  Future<void> stop();
}

/// Mock mode has no gateway to listen to: the mock sources update their own
/// lists, so this reports [LiveStatus.online] and never sends an event.
class MockLiveUpdates implements LiveUpdates {
  const MockLiveUpdates();

  @override
  Stream<SseEvent> get events => const Stream.empty();

  @override
  LiveStatus get status => LiveStatus.online;

  @override
  Stream<LiveStatus> get statusChanges => const Stream.empty();

  @override
  void start() {}

  @override
  Future<void> stop() async {}
}
