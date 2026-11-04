import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';
import 'package:mirsad/core/network/live/sse_live_updates.dart';

/// Answers each request with the next scripted reply: an HTTP status or a
/// body stream the test writes to. Once the script runs out, the stream
/// stays open and silent.
class _StreamAdapter implements HttpClientAdapter {
  final List<Object> script = [];
  final List<RequestOptions> requests = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    final reply = script.isEmpty
        ? StreamController<Uint8List>()
        : script.removeAt(0);
    if (reply is int) return ResponseBody.fromString('{}', reply);
    final body = reply as StreamController<Uint8List>;
    unawaited(cancelFuture?.then((_) => body.close()));
    return ResponseBody(
      body.stream,
      200,
      headers: {
        Headers.contentTypeHeader: ['text/event-stream'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

extension on StreamController<Uint8List> {
  void send(String text) => add(Uint8List.fromList(utf8.encode(text)));
}

void main() {
  late _StreamAdapter adapter;
  late List<int> attempts;
  late SseLiveUpdates live;

  SseLiveUpdates build({Duration idleTimeout = const Duration(minutes: 1)}) {
    return SseLiveUpdates(
      Dio(BaseOptions(baseUrl: 'http://gateway.test'))
        ..httpClientAdapter = adapter,
      backoff: (attempt) {
        attempts.add(attempt);
        return Duration.zero;
      },
      idleTimeout: idleTimeout,
    );
  }

  setUp(() {
    adapter = _StreamAdapter();
    attempts = [];
    live = build();
  });

  tearDown(() => live.dispose());

  Future<void> until(bool Function() condition) async {
    for (var i = 0; i < 200 && !condition(); i++) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    expect(condition(), isTrue);
  }

  test('backs off 1, 2, 4, 8, 16, then 30 seconds', () {
    expect(
      [for (var i = 0; i < 8; i++) exponentialBackoff(i).inSeconds],
      [1, 2, 4, 8, 16, 30, 30, 30],
    );
  });

  test('asks for the event stream and goes online on ready', () async {
    final body = StreamController<Uint8List>();
    addTearDown(body.close);
    adapter.script.add(body);
    final events = <SseEvent>[];
    live.events.listen(events.add);

    expect(live.status, LiveStatus.offline);
    live.start();
    expect(live.status, LiveStatus.connecting);

    body.send(': ping\n\nevent: ready\ndata: {"role":"approver"}\n\n');
    await until(() => live.status == LiveStatus.online);
    body.send('event: approval.requested\ndata: {"id":"apr_1"}\n\n');
    await until(() => events.length == 2);

    expect(events.last, const SseEvent('approval.requested', '{"id":"apr_1"}'));
    final request = adapter.requests.single;
    expect(request.path, '/api/stream');
    expect(request.headers['Accept'], 'text/event-stream');
  });

  test('reconnects when the stream ends, and when it is refused', () async {
    final first = StreamController<Uint8List>();
    final third = StreamController<Uint8List>();
    addTearDown(third.close);
    adapter.script.addAll([first, 401, third]);
    final statuses = <LiveStatus>[];
    live.statusChanges.listen(statuses.add);

    live.start();
    first.send('event: ready\ndata: {}\n\n');
    await until(() => live.status == LiveStatus.online);
    await first.close();

    await until(() => adapter.requests.length == 3);
    third.send('event: ready\ndata: {}\n\n');
    await until(() => live.status == LiveStatus.online);

    expect(statuses, [
      LiveStatus.connecting,
      LiveStatus.online,
      LiveStatus.reconnecting,
      LiveStatus.online,
    ]);
    // The 401 was a second failure in a row; ready resets the count.
    expect(attempts, [0, 1]);
  });

  test('treats a silent connection as dropped', () async {
    await live.dispose();
    live = build(idleTimeout: const Duration(milliseconds: 30));
    final silent = StreamController<Uint8List>();
    addTearDown(silent.close);
    adapter.script.add(silent);

    live.start();
    silent.send('event: ready\ndata: {}\n\n');
    await until(() => live.status == LiveStatus.online);

    await until(() => adapter.requests.length == 2);
    expect(live.status, LiveStatus.reconnecting);
  });

  test('stop closes the stream and stops retrying', () async {
    // Keeps failing, so without stop() requests would keep coming.
    adapter.script.addAll(List.filled(10000, 500));
    live.start();
    await until(() => adapter.requests.length >= 2);

    await live.stop();
    // A request Dio had already queued may still land; then nothing more.
    await Future<void>.delayed(const Duration(milliseconds: 20));
    final made = adapter.requests.length;
    await Future<void>.delayed(const Duration(milliseconds: 60));

    expect(live.status, LiveStatus.offline);
    expect(adapter.requests.length, made);
  });

  test('start twice opens one connection', () async {
    live
      ..start()
      ..start();
    await until(() => adapter.requests.isNotEmpty);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(adapter.requests, hasLength(1));
  });
}
