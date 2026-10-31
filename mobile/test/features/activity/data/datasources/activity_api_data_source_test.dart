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

  test('GET /events asks for 100 events and parses them', () async {
    adapter.on('GET', '/events', body: [eventJson(), eventJson()]);

    final events = await source.watchEvents().first;

    expect(events, hasLength(2));
    expect(adapter.requests.single.queryParameters, {'limit': 100});
  });

  test('a 401 from the gateway is an UnauthorizedException', () async {
    adapter.on('GET', '/events', status: 401, body: {'detail': 'expired'});

    await expectLater(
      source.watchEvents(),
      emitsError(isA<UnauthorizedException>()),
    );
  });
}
