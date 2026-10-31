/// Errors thrown by data sources.
///
/// Repositories catch these (see `guard`) and return a matching `Failure`, so
/// they never reach the presentation layer.
sealed class AppException implements Exception {
  const AppException([this.message]);

  /// Developer-facing detail, for logs.
  final String? message;

  @override
  String toString() => '$runtimeType(${message ?? ''})';
}

/// No connection, a timeout, or the request was cancelled.
final class NetworkException extends AppException {
  const NetworkException([super.message]);
}

/// The server answered with an error not covered by a more specific type.
final class ServerException extends AppException {
  const ServerException({this.statusCode, String? message}) : super(message);

  final int? statusCode;
}

/// Missing, invalid or expired credentials (HTTP 401 / 403).
final class UnauthorizedException extends AppException {
  const UnauthorizedException([super.message]);
}

/// The requested item does not exist (HTTP 404).
final class NotFoundException extends AppException {
  const NotFoundException([super.message]);
}

/// The item is not in a state that allows the request, e.g. a decision sent
/// for an approval that was already decided or has expired (HTTP 409).
final class ConflictException extends AppException {
  const ConflictException([super.message]);
}

/// Sign-in was refused because the email or password is wrong.
final class InvalidCredentialsException extends AppException {
  const InvalidCredentialsException([super.message]);
}

/// A response did not match the expected shape.
final class DataFormatException extends AppException {
  const DataFormatException([super.message]);
}
