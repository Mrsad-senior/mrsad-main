import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/network/live/sse_event.dart';
import 'package:mirsad/core/network/live/sse_parser.dart';

Future<List<SseEvent>> _parse(String body) {
  return Stream.value(
    body,
  ).transform(const LineSplitter()).transform(sseEventsFromLines()).toList();
}

void main() {
  test('reads named events and their data', () async {
    final events = await _parse(
      'event: ready\r\ndata: {"user":"admin","role":"admin"}\r\n\r\n'
      'event: approval.requested\r\ndata: {"id":"apr_1"}\r\n\r\n',
    );
    expect(events, const [
      SseEvent('ready', '{"user":"admin","role":"admin"}'),
      SseEvent('approval.requested', '{"id":"apr_1"}'),
    ]);
  });

  test('skips the heartbeat comment and empty events', () async {
    final events = await _parse(
      ': ping\n\n\n\nevent: audit.event\ndata: {}\n\n',
    );
    expect(events, const [SseEvent('audit.event', '{}')]);
  });

  test('joins data lines and defaults the event name to message', () async {
    final events = await _parse('data: first\ndata:second\n\n');
    expect(events, const [SseEvent('message', 'first\nsecond')]);
  });

  test('drops an event the stream cut off before its blank line', () async {
    expect(await _parse('event: ready\ndata: {}\n'), isEmpty);
  });

  test('knows which events are about approvals', () {
    expect(const SseEvent('approval.decided', '{}').isApproval, isTrue);
    expect(const SseEvent('audit.event', '{}').isApproval, isFalse);
  });
}
