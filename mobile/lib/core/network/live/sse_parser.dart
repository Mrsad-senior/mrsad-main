import 'dart:async';

import 'package:mirsad/core/network/live/sse_event.dart';

/// Turns the lines of a `text/event-stream` body into [SseEvent]s, following
/// the HTML Server-Sent Events format. A blank line ends an event. Comment
/// lines (the gateway's `: ping` heartbeat) are skipped, and so are the `id`
/// and `retry` fields, which the gateway does not send.
StreamTransformer<String, SseEvent> sseEventsFromLines() {
  return StreamTransformer.fromBind((lines) async* {
    var event = '';
    final data = <String>[];
    await for (final line in lines) {
      if (line.isEmpty) {
        if (data.isNotEmpty) {
          yield SseEvent(event.isEmpty ? 'message' : event, data.join('\n'));
        }
        event = '';
        data.clear();
        continue;
      }
      if (line.startsWith(':')) continue;
      final colon = line.indexOf(':');
      final field = colon < 0 ? line : line.substring(0, colon);
      var value = colon < 0 ? '' : line.substring(colon + 1);
      if (value.startsWith(' ')) value = value.substring(1);
      switch (field) {
        case 'event':
          event = value;
        case 'data':
          data.add(value);
      }
    }
  });
}
