import 'package:equatable/equatable.dart';

/// Why an operation did not succeed, as seen by the domain and presentation
/// layers. Returned inside `Either<Failure, T>`, never thrown.
sealed class Failure extends Equatable {
  const Failure([this.detail]);

  /// Developer-facing detail for logs. Never shown to reviewers as-is.
  final String? detail;

  @override
  List<Object?> get props => [detail];
}

final class NetworkFailure extends Failure {
  const NetworkFailure([super.detail]);
}

final class ServerFailure extends Failure {
  const ServerFailure({this.statusCode, String? detail}) : super(detail);

  final int? statusCode;

  @override
  List<Object?> get props => [statusCode, detail];
}

final class UnauthorizedFailure extends Failure {
  const UnauthorizedFailure([super.detail]);
}

final class NotFoundFailure extends Failure {
  const NotFoundFailure([super.detail]);
}

/// The item changed state before the request arrived, e.g. an approval that
/// was already decided or has expired.
final class ConflictFailure extends Failure {
  const ConflictFailure([super.detail]);
}

final class InvalidCredentialsFailure extends Failure {
  const InvalidCredentialsFailure([super.detail]);
}

final class DataFormatFailure extends Failure {
  const DataFormatFailure([super.detail]);
}

final class UnexpectedFailure extends Failure {
  const UnexpectedFailure([super.detail]);
}
