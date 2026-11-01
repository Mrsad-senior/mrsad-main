import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/activity/data/datasources/activity_api_data_source.dart';

import '../../../../helpers/fake_http_adapter.dart';
import '../../activity_fixtures.dart';

void main() {
  late FakeHttpAdapter adapter;
  late ActivityApiDataSource source;

  setUp(() {
    adapter = FakeHttpAdapter();
    source = ActivityApiDataSource(
      fakeDio(adapter),
      pollInterval: const Duration(hours: 1),
    );
  });

  tearDown(() => source.dispose());

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
