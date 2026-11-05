import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';

DioException _badResponse(int statusCode, [Object? body]) {
  final options = RequestOptions(path: '/approvals/apr_1');
  return DioException(
    requestOptions: options,
    type: DioExceptionType.badResponse,
    response: Response<Object?>(
      requestOptions: options,
      statusCode: statusCode,
      data: body,
    ),
  );
}

void main() {
  test('maps timeouts and connection errors to NetworkException', () {
    for (final type in [
      DioExceptionType.connectionTimeout,
      DioExceptionType.receiveTimeout,
      DioExceptionType.connectionError,
    ]) {
      final error = DioException(requestOptions: RequestOptions(), type: type);
      expect(mapDioException(error), isA<NetworkException>());
    }
  });

  test('maps 401 and 403 to UnauthorizedException', () {
    expect(mapDioException(_badResponse(401)), isA<UnauthorizedException>());
    expect(mapDioException(_badResponse(403)), isA<UnauthorizedException>());
  });

  test('maps 404 to NotFoundException', () {
    expect(mapDioException(_badResponse(404)), isA<NotFoundException>());
  });

  test('maps 409 to ConflictException with the FastAPI detail', () {
    final mapped = mapDioException(
      _badResponse(409, {'detail': 'Approval is no longer held'}),
    );
    expect(mapped, isA<ConflictException>());
    expect(mapped.message, 'Approval is no longer held');
  });

  test('maps other statuses to ServerException with the status code', () {
    final mapped = mapDioException(_badResponse(503));
    expect(mapped, isA<ServerException>());
    expect((mapped as ServerException).statusCode, 503);
  });

  test('callGateway rethrows Dio errors as AppExceptions', () async {
    await expectLater(
      callGateway<void>(() async => throw _badResponse(404)),
      throwsA(isA<NotFoundException>()),
    );
  });
}
