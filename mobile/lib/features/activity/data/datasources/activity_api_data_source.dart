import 'dart:async';

import 'package:dio/dio.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/core/network/polling_stream.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';

/// The activity feed: the newest decision events from
/// `GET /api/audit/events`, polled because the API has no push updates.
///
/// The gateway lets only admins and auditors read audit events; approvers get
/// 403. docs/API_CONTRACT.md proposes a feed approvers can read.
class ActivityApiDataSource implements ActivityDataSource {
  ActivityApiDataSource(
    this._dio, {
    this.pollInterval = const Duration(seconds: 15),
  });

  static const path = '/api/audit/events';
  static const pageSize = 100;

  final Dio _dio;
  final Duration pollInterval;
  final StreamController<List<ActivityEventModel>> _updates =
      StreamController.broadcast();

  @override
  Stream<List<ActivityEventModel>> watchEvents() {
    return pollingStream(
      fetch: _fetch,
      interval: pollInterval,
      updates: _updates.stream,
    );
  }

  @override
  Future<void> refresh() async => _updates.add(await _fetch());

  Future<void> dispose() => _updates.close();

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
