import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/live/live_refresh_stream.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';

import '../../../helpers/fake_live_updates.dart';

void main() {
  late FakeLiveUpdates live;
  late int fetches;

  setUp(() {
    live = FakeLiveUpdates();
    fetches = 0;
  });

  tearDown(() => live.close());

  Stream<int> follow({
    Future<int> Function()? fetch,
    Duration fallbackInterval = const Duration(hours: 1),
    Stream<int>? updates,
  }) {
    return liveRefreshStream<int>(
      fetch: fetch ?? () async => ++fetches,
      live: live,
      isRelevant: (event) => event.event == SseEvent.approvalRequested,
      fallbackInterval: fallbackInterval,
      updates: updates,
    );
  }

  test('fetches as soon as it is listened to', () async {
    expect(await follow().first, 1);
  });

  test('fetches again for relevant events only', () async {
    final values = <int>[];
    final subscription = follow().listen(values.add);
    await settle();

    live
      ..emit(SseEvent.auditEvent)
      ..emit(SseEvent.approvalRequested);
    await settle();

    expect(values, [1, 2]);
    await subscription.cancel();
  });

  test('does not poll while online', () async {
    final subscription = follow(
      fallbackInterval: const Duration(milliseconds: 10),
    ).listen((_) {});
    await Future<void>.delayed(const Duration(milliseconds: 45));

    expect(fetches, 1);
    await subscription.cancel();
  });

  test('polls while the stream is down and catches up when back', () async {
    live.setStatus(LiveStatus.reconnecting);
    final subscription = follow(
      fallbackInterval: const Duration(milliseconds: 10),
    ).listen((_) {});
    await Future<void>.delayed(const Duration(milliseconds: 45));
    expect(fetches, greaterThan(2));

    live.setStatus(LiveStatus.online);
    await settle();
    final afterReconnect = fetches;
    await Future<void>.delayed(const Duration(milliseconds: 45));

    expect(fetches, afterReconnect);
    await subscription.cancel();
  });

  test('coalesces events that arrive during a fetch', () async {
    var gate = Completer<void>();
    final subscription = follow(
      fetch: () async {
        fetches++;
        await gate.future;
        return fetches;
      },
    ).listen((_) {});
    await settle();
    expect(fetches, 1);

    live
      ..emit(SseEvent.approvalRequested)
      ..emit(SseEvent.approvalRequested)
      ..emit(SseEvent.approvalRequested);
    await settle();
    gate.complete();
    gate = Completer<void>()..complete();
    await settle();
    await settle();

    expect(fetches, 2);
    await subscription.cancel();
  });

  test('keeps going after a failed fetch', () async {
    final stream = follow(
      fetch: () async {
        fetches++;
        if (fetches == 1) throw const NetworkException();
        return fetches;
      },
    );
    final expectation = expectLater(
      stream,
      emitsInOrder([emitsError(isA<NetworkException>()), 2]),
    );
    await settle();
    live.emit(SseEvent.approvalRequested);
    await expectation;
  });

  test('forwards values pushed to updates', () async {
    final updates = StreamController<int>.broadcast();
    final expectation = expectLater(
      follow(updates: updates.stream),
      emitsInOrder([1, 7]),
    );
    await settle();
    updates.add(7);
    await expectation;
    await updates.close();
  });
}
