import 'dart:async';

import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/core/network/live/live_refresh_stream.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/approval_wire_values.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';

/// Approvals from the Mirsad gateway (docs/api.md, "Approvals"). The gateway
/// only shows them to approvers and admins. The pending list is fetched
/// again on every `approval.requested` / `approval.decided` event from the
/// live stream, and polled while the stream is down.
class ApprovalsApiDataSource
    implements ApprovalsReadDataSource, ApprovalDecisionDataSource {
  ApprovalsApiDataSource(
    this._dio,
    this._live, {
    this.pollInterval = const Duration(seconds: 15),
  });

  static const path = '/api/approvals';
  static const pageSize = 100;

  final Dio _dio;
  final LiveUpdates _live;

  /// How often to poll while the live stream is down.
  final Duration pollInterval;
  final StreamController<List<ApprovalModel>> _updates =
      StreamController.broadcast();

  @override
  Stream<List<ApprovalModel>> watchPending() {
    return liveRefreshStream(
      fetch: _fetchPending,
      live: _live,
      isRelevant: (event) => event.isApproval,
      fallbackInterval: pollInterval,
      updates: _updates.stream,
    );
  }

  @override
  Future<void> refreshPending() async => _updates.add(await _fetchPending());

  @override
  Future<ApprovalModel> getApproval(String id) {
    return callGateway(() async {
      final response = await _dio.get<Map<String, dynamic>>(_path(id));
      return ApprovalModel.fromJson(_body(response));
    });
  }

  @override
  Future<ApprovalModel> submitDecision(
    String id,
    DecisionRequestModel request,
  ) async {
    final updated = await callGateway(() async {
      final response = await _dio.post<Map<String, dynamic>>(
        '${_path(id)}/decision',
        data: request.toJson(),
      );
      return ApprovalModel.fromJson(_body(response));
    });
    // Drop the decided approval from the list now instead of waiting for
    // the stream's `approval.decided`. A failure here is ignored.
    unawaited(refreshPending().catchError((Object _) {}));
    return updated;
  }

  Future<void> dispose() => _updates.close();

  Future<List<ApprovalModel>> _fetchPending() {
    return callGateway(() async {
      final response = await _dio.get<List<dynamic>>(
        path,
        queryParameters: {'status': pendingStatus, 'limit': pageSize},
      );
      return [
        for (final item in response.data ?? const <dynamic>[])
          ApprovalModel.fromJson(item as Map<String, dynamic>),
      ];
    });
  }

  String _path(String id) => '$path/${Uri.encodeComponent(id)}';

  Map<String, dynamic> _body(Response<Map<String, dynamic>> response) {
    return response.data ??
        (throw const DataFormatException('Empty approval response'));
  }
}
