import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/home/data/datasources/home_api_data_source.dart';
import 'package:mirsad/features/home/data/datasources/home_mock_data_source.dart';

import '../../../../helpers/fake_http_adapter.dart';
import '../../../../helpers/fake_live_updates.dart';
import '../../home_fixtures.dart';

void main() {
  group('HomeApiDataSource', () {
    late FakeHttpAdapter adapter;
    late FakeLiveUpdates live;
    late HomeApiDataSource source;

    setUp(() {
      adapter = FakeHttpAdapter();
      live = FakeLiveUpdates();
      source = HomeApiDataSource(
        fakeDio(adapter),
        live,
        pollInterval: const Duration(hours: 1),
      );
    });

    tearDown(() async {
      await source.dispose();
      await live.close();
    });

    test('GET /api/stats/overview?hours=24 feeds watchOverview', () async {
      adapter.on('GET', '/api/stats/overview', body: overviewJson());

      final model = await source.watchOverview().first;

      expect(model.totalCalls, 14);
      expect(adapter.requests.single.queryParameters, {'hours': 24});
    });

    test('fetches again on approvals and audit events', () async {
      adapter.on('GET', '/api/stats/overview', body: overviewJson());
      final subscription = source.watchOverview().listen((_) {});
      await eventually(() => adapter.requests.length == 1);

      live.emit('approval.decided');
      await eventually(() => adapter.requests.length == 2);
      live.emit('audit.event');
      await eventually(() => adapter.requests.length == 3);
      await subscription.cancel();
    });

    test('a failed fetch is a stream error', () async {
      adapter.on('GET', '/api/stats/overview', status: 500);
      await expectLater(
        source.watchOverview(),
        emitsError(isA<ServerException>()),
      );
    });
  });

  group('HomeMockDataSource', () {
    test('emits the demo day, again on refresh', () async {
      final source = HomeMockDataSource(latency: Duration.zero);
      addTearDown(source.dispose);
      final expectation = expectLater(
        source.watchOverview().map((model) => model.totalCalls),
        emitsInOrder([1302, 1302]),
      );
      await settle();
      await source.refresh();
      await expectation;
    });
  });
}
