import 'dart:async';

import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/core/network/polling_stream.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';

/// Approvals from the Mirsad gateway (see docs/API_CONTRACT.md). The API has
/// no push updates, so the pending list is polled.
class ApprovalsApiDataSource
    implements ApprovalsReadDataSource, ApprovalDecisionDataSource {
  ApprovalsApiDataSource(
    this._dio, {
    this.pollInterval = const Duration(seconds: 15),
  });

  final Dio _dio;
  final Duration pollInterval;
  final StreamController<List<ApprovalModel>> _updates =
      StreamController.broadcast();

  @override
  Stream<List<ApprovalModel>> watchPending() {
    return pollingStream(
      fetch: _fetchPending,
      interval: pollInterval,
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
        _path(id),
        data: request.toJson(),
      );
      return ApprovalModel.fromJson(_body(response));
    });
    // Drop the decided approval from the list now instead of at the next
    // poll. A failure here only delays that, so it is ignored.
    unawaited(refreshPending().catchError((Object _) {}));
    return updated;
  }

  Future<void> dispose() => _updates.close();

  Future<List<ApprovalModel>> _fetchPending() {
    return callGateway(() async {
      final response = await _dio.get<List<dynamic>>('/approvals/pending');
      return [
        for (final item in response.data ?? const <dynamic>[])
          ApprovalModel.fromJson(item as Map<String, dynamic>),
      ];
    });
  }

  String _path(String id) => '/approvals/${Uri.encodeComponent(id)}';

  Map<String, dynamic> _body(Response<Map<String, dynamic>> response) {
    return response.data ??
        (throw const DataFormatException('Empty approval response'));
  }
}
