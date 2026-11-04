import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:dio/dio.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';
import 'package:mirsad/core/network/live/sse_parser.dart';

/// Waits 1, 2, 4, 8 and 16 seconds, then 30 seconds between attempts.
Duration exponentialBackoff(int attempt) =>
    Duration(seconds: min(30, 1 << min(attempt, 5)));

/// Listens to the gateway's `GET /api/stream` (Server-Sent Events).
///
/// The gateway Dio adds `Authorization: Bearer`, which the stream requires
/// (it does not accept a token in the query string). A dropped, refused or
/// silent connection is retried with [backoff]; the attempt counter resets
/// once the gateway sends `ready`.
class SseLiveUpdates implements LiveUpdates {
  SseLiveUpdates(
    this._dio, {
    this._backoff = exponentialBackoff,
    this.idleTimeout = const Duration(seconds: 45),
  });

  static const path = '/api/stream';

  final Dio _dio;
  final Duration Function(int attempt) _backoff;

  /// The gateway sends a `: ping` comment every 15 seconds, so this long
  /// without a byte means the connection is dead even if the socket is not.
  final Duration idleTimeout;

  final StreamController<SseEvent> _events = StreamController.broadcast();
  final StreamController<LiveStatus> _statusChanges =
      StreamController.broadcast();

  LiveStatus _status = LiveStatus.offline;

  /// Bumped by [start] and [stop], so a loop from an earlier session ends.
  int _session = 0;
  CancelToken? _cancel;
  Timer? _retryTimer;
  Completer<void>? _retryWait;

  @override
  Stream<SseEvent> get events => _events.stream;

  @override
  LiveStatus get status => _status;

  @override
  Stream<LiveStatus> get statusChanges => _statusChanges.stream;

  @override
  void start() {
    if (_status != LiveStatus.offline) return;
    final session = ++_session;
    _set(LiveStatus.connecting);
    unawaited(_run(session));
  }

  @override
  Future<void> stop() async {
    _session++;
    _cancel?.cancel();
    _retryTimer?.cancel();
    final wait = _retryWait;
    if (wait != null && !wait.isCompleted) wait.complete();
    _set(LiveStatus.offline);
  }

  Future<void> dispose() async {
    await stop();
    await _events.close();
    await _statusChanges.close();
  }

  Future<void> _run(int session) async {
    var attempt = 0;
    while (session == _session) {
      try {
        await _listen(session, onReady: () => attempt = 0);
      } on Object {
        // Dropped, refused, timed out or unauthorised: retry below.
      }
      if (session != _session) return;
      _set(LiveStatus.reconnecting);
      await _wait(_backoff(attempt++));
    }
  }

  Future<void> _listen(int session, {required void Function() onReady}) async {
    final cancel = _cancel = CancelToken();
    try {
      final response = await _dio.get<ResponseBody>(
        path,
        cancelToken: cancel,
        options: Options(
          responseType: ResponseType.stream,
          receiveTimeout: idleTimeout,
          headers: {'Accept': 'text/event-stream'},
        ),
      );
      final body = response.data;
      if (body == null) return;
      final events = body.stream
          .timeout(idleTimeout)
          .cast<List<int>>()
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .transform(sseEventsFromLines());
      await for (final event in events) {
        if (session != _session) return;
        if (event.event == SseEvent.ready) {
          onReady();
          _set(LiveStatus.online);
        }
        _events.add(event);
      }
    } finally {
      cancel.cancel();
    }
  }

  Future<void> _wait(Duration delay) {
    final done = _retryWait = Completer<void>();
    _retryTimer = Timer(delay, () {
      if (!done.isCompleted) done.complete();
    });
    return done.future;
  }

  void _set(LiveStatus status) {
    if (status == _status) return;
    _status = status;
    if (!_statusChanges.isClosed) _statusChanges.add(status);
  }
}
