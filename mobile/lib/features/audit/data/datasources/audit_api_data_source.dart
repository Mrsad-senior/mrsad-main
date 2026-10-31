import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/features/audit/data/datasources/audit_data_source.dart';
import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';

/// `GET /audit/verify` on the Mirsad gateway.
class AuditApiDataSource implements AuditDataSource {
  const AuditApiDataSource(this._dio);

  final Dio _dio;

  @override
  Future<AuditChainStatusModel> verify() {
    return callGateway(() async {
      final response = await _dio.get<Map<String, dynamic>>('/audit/verify');
      final body =
          response.data ??
          (throw const DataFormatException('Empty audit response'));
      return AuditChainStatusModel.fromJson(body);
    });
  }
}
