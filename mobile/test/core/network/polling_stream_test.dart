import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/polling_stream.dart';

void main() {
  test('fetches as soon as it is listened to', () async {
    var calls = 0;
    final stream = pollingStream(
      fetch: () async => ++calls,
      interval: const Duration(hours: 1),
    );
    expect(await stream.first, 1);
  });

  test('forwards values pushed to updates', () async {
    final updates = StreamController<int>.broadcast();
    final stream = pollingStream(
      fetch: () async => 0,
      interval: const Duration(hours: 1),
      updates: updates.stream,
    );
    final expectation = expectLater(stream, emitsInOrder([0, 7]));
    await Future<void>.delayed(Duration.zero);
    updates.add(7);
    await expectation;
    await updates.close();
  });

  test('keeps polling after a failed fetch', () async {
    var calls = 0;
    final stream = pollingStream<int>(
      fetch: () async {
        calls++;
        if (calls == 1) throw const NetworkException();
        return calls;
      },
      interval: const Duration(milliseconds: 10),
    );
    await expectLater(
      stream,
      emitsInOrder([emitsError(isA<NetworkException>()), 2]),
    );
  });
}
