import 'dart:io';

import 'package:mirsad/core/errors/exceptions.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Runs a Supabase call and rethrows its errors as [AppException]s.
Future<T> callSupabase<T>(Future<T> Function() request) async {
  try {
    return await request();
  } catch (error) {
    throw mapSupabaseError(error);
  }
}

/// Maps a Supabase error to an [AppException]. Errors it does not recognise
/// are returned unchanged and end up as an unexpected failure.
Object mapSupabaseError(Object error) {
  return switch (error) {
    AppException() => error,
    // Older Auth servers send a bare 400 without an error code.
    AuthApiException(:final code, :final statusCode)
        when code == 'invalid_credentials' ||
            (code == null && statusCode == '400') =>
      InvalidCredentialsException(error.message),
    AuthRetryableFetchException() => NetworkException(error.message),
    AuthException() => UnauthorizedException(error.message),
    // PGRST116: `.single()` found no row.
    PostgrestException(code: 'PGRST116') => NotFoundException(error.message),
    // 42501: blocked by Row Level Security.
    PostgrestException(code: '42501') => UnauthorizedException(error.message),
    PostgrestException() => ServerException(message: error.message),
    RealtimeSubscribeException() => NetworkException(error.toString()),
    SocketException() => NetworkException(error.message),
    _ => error,
  };
}
