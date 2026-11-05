import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

/// Serves canned JSON responses to Dio, keyed by method and path, and
/// records every request.
class FakeHttpAdapter implements HttpClientAdapter {
  final Map<String, (int, Object?)> _responses = {};
  final List<RequestOptions> requests = [];

  void on(String method, String path, {int status = 200, Object? body}) {
    _responses['$method $path'] = (status, body);
  }

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    final (status, body) =
        _responses['${options.method} ${options.path}'] ??
        (404, {'detail': 'No fake response for ${options.path}'});
    return ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Dio fakeDio(FakeHttpAdapter adapter) {
  return Dio(BaseOptions(baseUrl: 'http://gateway.test'))
    ..httpClientAdapter = adapter;
}
