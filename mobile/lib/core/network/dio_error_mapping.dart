import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';

/// Runs a gateway request and rethrows Dio errors as [AppException]s.
Future<T> callGateway<T>(Future<T> Function() request) async {
  try {
    return await request();
  } on DioException catch (error) {
    throw mapDioException(error);
  }
}

/// Maps a Dio error to the [AppException] the repositories understand.
AppException mapDioException(DioException error) {
  switch (error.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.transformTimeout:
    case DioExceptionType.connectionError:
    case DioExceptionType.cancel:
    case DioExceptionType.badCertificate:
      return NetworkException(error.message);
    case DioExceptionType.badResponse:
      return _fromResponse(error.response);
    case DioExceptionType.unknown:
      final cause = error.error;
      if (cause is AppException) return cause;
      if (cause is FormatException) return DataFormatException(cause.message);
      return NetworkException(error.message ?? cause?.toString());
  }
}

AppException _fromResponse(Response<Object?>? response) {
  final statusCode = response?.statusCode;
  final detail = _detail(response?.data);
  return switch (statusCode) {
    401 || 403 => UnauthorizedException(detail),
    404 => NotFoundException(detail),
    409 => ConflictException(detail),
    _ => ServerException(statusCode: statusCode, message: detail),
  };
}

/// FastAPI puts the error message in `{"detail": "..."}`.
String? _detail(Object? body) {
  if (body is Map<String, Object?>) {
    final detail = body['detail'];
    if (detail is String) return detail;
  }
  if (body is String && body.isNotEmpty) return body;
  return null;
}
