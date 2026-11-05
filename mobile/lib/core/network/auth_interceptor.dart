import 'package:dio/dio.dart';

/// Returns the signed-in reviewer's access token, or null when signed out.
typedef AccessTokenReader = Future<String?> Function();

/// Adds `Authorization: Bearer <token>` to every gateway request.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._readToken);

  final AccessTokenReader _readToken;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await _readToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }
}
