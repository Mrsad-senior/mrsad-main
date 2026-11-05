import 'dart:async';

import 'package:mirsad/features/home/data/datasources/home_data_source.dart';
import 'package:mirsad/features/home/data/models/overview_stats_model.dart';
import 'package:mirsad/features/home/data/models/tool_stats_model.dart';

/// A busy day at the finance demo's bank, in the gateway's shape.
class HomeMockDataSource implements HomeDataSource {
  HomeMockDataSource({this.latency = const Duration(milliseconds: 300)});

  /// Simulated network delay.
  final Duration latency;

  final StreamController<OverviewStatsModel> _updates =
      StreamController.broadcast();

  static const demo = OverviewStatsModel(
    hours: 24,
    totalCalls: 1302,
    allowed: 1284,
    denied: 12,
    approvalsRequired: 6,
    approvalsPending: 2,
    injectionsDetected: 9,
    medianLatencyMs: 1.4,
    p95LatencyMs: 6.8,
    auditOk: true,
    byTool: [
      ToolStatsModel(tool: 'get_account_balance', allowed: 812),
      ToolStatsModel(tool: 'send_email', allowed: 401, denied: 3, approval: 2),
      ToolStatsModel(
        tool: 'transfer_funds',
        allowed: 71,
        denied: 9,
        approval: 4,
      ),
    ],
  );

  @override
  Stream<OverviewStatsModel> watchOverview() async* {
    await Future<void>.delayed(latency);
    yield demo;
    yield* _updates.stream;
  }

  @override
  Future<void> refresh() async {
    await Future<void>.delayed(latency);
    _updates.add(demo);
  }

  Future<void> dispose() => _updates.close();
}
