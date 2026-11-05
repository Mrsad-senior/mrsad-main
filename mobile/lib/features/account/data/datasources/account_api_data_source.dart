import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/features/account/data/datasources/account_data_source.dart';
import 'package:mirsad/features/account/data/models/account_model.dart';

/// `GET /api/auth/me`, open to every role. The gateway reloads the user on
/// every request, so a changed role or display name shows up here at once.
class AccountApiDataSource implements AccountDataSource {
  const AccountApiDataSource(this._dio);

  static const path = '/api/auth/me';

  final Dio _dio;

  @override
  Future<AccountModel> me() {
    return callGateway(() async {
      final response = await _dio.get<Map<String, dynamic>>(path);
      return AccountModel.fromJson(
        response.data ??
            (throw const DataFormatException('Empty account response')),
      );
    });
  }
}
