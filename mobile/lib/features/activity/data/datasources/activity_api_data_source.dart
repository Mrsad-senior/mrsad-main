import 'dart:async';

import 'package:dio/dio.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/core/network/polling_stream.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';

/// The activity feed from `GET /events`, polled because the API has no push
/// updates.
class ActivityApiDataSource implements ActivityDataSource {
  ActivityApiDataSource(
    this._dio, {
    this.pollInterval = const Duration(seconds: 15),
  });

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
      final response = await _dio.get<List<dynamic>>(
        '/events',
        queryParameters: {'limit': pageSize},
      );
      return [
        for (final item in response.data ?? const <dynamic>[])
          ActivityEventModel.fromJson(item as Map<String, dynamic>),
      ];
    });
  }
}
