import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:mirsad/core/network/auth_interceptor.dart';

/// Builds the Dio instance used to talk to the Mirsad gateway.
Dio createGatewayDio({
  required String baseUrl,
  required AccessTokenReader readToken,
}) {
  final dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
      contentType: Headers.jsonContentType,
      headers: const {'Accept': 'application/json'},
    ),
  );
  dio.interceptors.add(AuthInterceptor(readToken));
  if (kDebugMode) {
    // Headers stay out of the log: they carry the reviewer's token.
    dio.interceptors.add(
      LogInterceptor(
        requestHeader: false,
        requestBody: true,
        responseBody: true,
        logPrint: (line) => debugPrint(line.toString()),
      ),
    );
  }
  return dio;
}
