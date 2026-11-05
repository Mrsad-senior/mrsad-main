import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/home/data/models/overview_stats_model.dart';

import '../../home_fixtures.dart';

void main() {
  test('parses the gateway overview', () {
    final stats = OverviewStatsModel.fromJson(overviewJson()).toEntity();
    expect(stats, overviewStats);
  });

  test('keeps an unchecked audit chain and missing latency as null', () {
    final json = overviewJson(auditOk: null)
      ..['median_latency_ms'] = null
      ..['p95_latency_ms'] = null
      ..remove('by_tool');

    final stats = OverviewStatsModel.fromJson(json).toEntity();

    expect(stats.auditOk, isNull);
    expect(stats.medianLatencyMs, isNull);
    expect(stats.tools, isEmpty);
  });

  test('busiestTools sorts by total calls', () {
    expect(overviewStats.busiestTools(2).map((tool) => tool.tool), [
      'get_account_balance',
      'transfer_funds',
    ]);
  });
}
