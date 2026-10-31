import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/activity/data/datasources/activity_mock_data_source.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

import '../../../../helpers/fake_clock.dart';

void main() {
  late ActivityMockDataSource source;

  setUp(() {
    source = ActivityMockDataSource(
      clock: FakeClock(testNow),
      latency: Duration.zero,
    );
  });

  tearDown(() => source.dispose());

  test('covers every decision in the finance demo', () async {
    final events = await source.watchEvents().first;
    final decisions = events.map((e) => e.decision).toSet();
    expect(decisions, GatewayDecision.values.toSet());
  });

  test('includes the Arabic injection that was denied', () async {
    final events = await source.watchEvents().first;
    final export = events.singleWhere(
      (e) => e.tool == 'export_customer_records',
    );
    expect(export.decision, GatewayDecision.denied);
    expect(export.summary, contains('تجاهل التعليمات السابقة'));
  });

  test('refresh re-emits the feed', () async {
    final expectation = expectLater(
      source.watchEvents().map((events) => events.length),
      emitsInOrder([7, 7]),
    );
    await Future<void>.delayed(Duration.zero);
    await source.refresh();
    await expectation;
  });
}
