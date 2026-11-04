import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/live/sse_event.dart';
import 'package:mirsad/features/activity/data/datasources/activity_api_data_source.dart';

import '../../../../helpers/fake_http_adapter.dart';
import '../../../../helpers/fake_live_updates.dart';
import '../../activity_fixtures.dart';

void main() {
  late FakeHttpAdapter adapter;
  late FakeLiveUpdates live;
  late ActivityApiDataSource source;

  setUp(() {
    adapter = FakeHttpAdapter();
    live = FakeLiveUpdates();
    source = ActivityApiDataSource(
      fakeDio(adapter),
      live,
      pollInterval: const Duration(hours: 1),
    );
  });

  tearDown(() async {
    await source.dispose();
    await live.close();
  });

  test('only new decision events trigger a fetch', () {
    expect(
      ActivityApiDataSource.isNewDecision(
        const SseEvent('audit.event', '{"event_type":"tool_call.decision"}'),
      ),
      isTrue,
    );
    expect(
      ActivityApiDataSource.isNewDecision(
        const SseEvent('audit.event', '{"event_type":"auth.login"}'),
      ),
      isFalse,
    );
    expect(
      ActivityApiDataSource.isNewDecision(
        const SseEvent('approval.requested', '{}'),
      ),
      isFalse,
    );
    expect(
      ActivityApiDataSource.isNewDecision(
        const SseEvent('audit.event', 'not json'),
      ),
      isFalse,
    );
  });

  test('fetches again when the stream reports a decision', () async {
    adapter.on('GET', '/api/audit/events', body: {'items': <Object>[]});
    final subscription = source.watchEvents().listen((_) {});
    await eventually(() => adapter.requests.length == 1);

    live.emit('audit.event', '{"event_type":"tool_call.decision"}');
    await eventually(() => adapter.requests.length == 2);
    await subscription.cancel();
  });

  test('GET /api/audit/events asks for 100 decision events', () async {
    adapter.on(
      'GET',
      '/api/audit/events',
      body: {
        'items': [eventJson(), eventJson()],
        'total': 2,
      },
    );

    final events = await source.watchEvents().first;

    expect(events, hasLength(2));
    expect(adapter.requests.single.queryParameters, {
      'event_type': 'tool_call.decision',
      'limit': 100,
    });
  });

  test('a 403 for an approver is an UnauthorizedException', () async {
    adapter.on(
      'GET',
      '/api/audit/events',
      status: 403,
      body: {'detail': 'Requires role: admin or auditor'},
    );

    await expectLater(
      source.watchEvents(),
      emitsError(isA<UnauthorizedException>()),
    );
  });
}
