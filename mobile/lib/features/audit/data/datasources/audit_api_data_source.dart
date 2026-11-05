import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/features/audit/data/datasources/audit_data_source.dart';
import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';

/// The audit chain status from `GET /api/stats/overview`, which every role
/// may read. `POST /api/audit/verify` also names the broken entry, but it is
/// for admins and auditors only and writes an audit event on every call.
class AuditApiDataSource implements AuditDataSource {
  const AuditApiDataSource(this._dio);

  static const path = '/api/stats/overview';

  final Dio _dio;

  @override
  Future<AuditChainStatusModel> verify() {
    return callGateway(() async {
      // The shortest window keeps the statistics computed alongside cheap.
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: {'hours': 1},
      );
      final body =
          response.data ??
          (throw const DataFormatException('Empty overview response'));
      final model = AuditChainStatusModel.fromJson(body);
      if (model.auditOk == null) {
        throw const ServerException(
          message: 'The gateway could not verify the audit chain',
        );
      }
      return model;
    });
  }
}
