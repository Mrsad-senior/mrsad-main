import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/core/network/live/live_refresh_stream.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/network/live/sse_event.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';

/// The activity feed: the newest decision events from
/// `GET /api/audit/events`, fetched again when the live stream reports a new
/// decision and polled while the stream is down.
///
/// The gateway lets only admins and auditors read audit events, so the app
/// shows this feed to those roles only.
class ActivityApiDataSource implements ActivityDataSource {
  ActivityApiDataSource(
    this._dio,
    this._live, {
    this.pollInterval = const Duration(seconds: 15),
  });

  static const path = '/api/audit/events';
  static const pageSize = 100;

  final Dio _dio;
  final LiveUpdates _live;

  /// How often to poll while the live stream is down.
  final Duration pollInterval;
  final StreamController<List<ActivityEventModel>> _updates =
      StreamController.broadcast();

  @override
  Stream<List<ActivityEventModel>> watchEvents() {
    return liveRefreshStream(
      fetch: _fetch,
      live: _live,
      isRelevant: isNewDecision,
      fallbackInterval: pollInterval,
      updates: _updates.stream,
    );
  }

  @override
  Future<void> refresh() async => _updates.add(await _fetch());

  Future<void> dispose() => _updates.close();

  /// Whether [event] is an `audit.event` for a gateway decision, the only
  /// kind the feed lists.
  static bool isNewDecision(SseEvent event) {
    if (event.event != SseEvent.auditEvent) return false;
    try {
      final data = jsonDecode(event.data);
      return data is Map && data['event_type'] == ActivityEventModel.eventType;
    } on FormatException {
      return false;
    }
  }

  Future<List<ActivityEventModel>> _fetch() {
    return callGateway(() async {
      // Newest first is the gateway's default order.
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: {
          'event_type': ActivityEventModel.eventType,
          'limit': pageSize,
        },
      );
      final items = response.data?['items'] as List<dynamic>? ?? const [];
      return [
        for (final item in items)
          ActivityEventModel.fromJson(item as Map<String, dynamic>),
      ];
    });
  }
}
