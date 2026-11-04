import 'dart:async';

import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/core/network/live/live_refresh_stream.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';
import 'package:mirsad/features/home/data/datasources/home_data_source.dart';
import 'package:mirsad/features/home/data/models/overview_stats_model.dart';

/// The last 24 hours from `GET /api/stats/overview`, which every role may
/// read. Fetched again whenever the live stream reports an approval or an
/// audit event (bursts lead to one fetch), polled while the stream is down.
class HomeApiDataSource implements HomeDataSource {
  HomeApiDataSource(
    this._dio,
    this._live, {
    this.pollInterval = const Duration(seconds: 30),
  });

  static const path = '/api/stats/overview';
  static const windowHours = 24;

  final Dio _dio;
  final LiveUpdates _live;

  /// How often to poll while the live stream is down.
  final Duration pollInterval;

  final StreamController<OverviewStatsModel> _updates =
      StreamController.broadcast();

  @override
  Stream<OverviewStatsModel> watchOverview() {
    return liveRefreshStream(
      fetch: _fetch,
      live: _live,
      isRelevant: (event) =>
          event.isApproval || event.event == SseEvent.auditEvent,
      fallbackInterval: pollInterval,
      updates: _updates.stream,
    );
  }

  @override
  Future<void> refresh() async => _updates.add(await _fetch());

  Future<void> dispose() => _updates.close();

  Future<OverviewStatsModel> _fetch() {
    return callGateway(() async {
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: {'hours': windowHours},
      );
      return OverviewStatsModel.fromJson(
        response.data ??
            (throw const DataFormatException('Empty overview response')),
      );
    });
  }
}
