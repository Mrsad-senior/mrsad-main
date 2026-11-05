import 'dart:async';

import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';

/// Maps anything a data source can throw to the matching [Failure].
Failure failureFrom(Object error) {
  return switch (error) {
    NetworkException(:final message) => NetworkFailure(message),
    ServerException(:final statusCode, :final message) => ServerFailure(
      statusCode: statusCode,
      detail: message,
    ),
    UnauthorizedException(:final message) => UnauthorizedFailure(message),
    NotFoundException(:final message) => NotFoundFailure(message),
    ConflictException(:final message) => ConflictFailure(message),
    InvalidCredentialsException(:final message) => InvalidCredentialsFailure(
      message,
    ),
    DataFormatException(:final message) => DataFormatFailure(message),
    FormatException(:final message) => DataFormatFailure(message),
    TypeError() => DataFormatFailure(error.toString()),
    _ => UnexpectedFailure(error.toString()),
  };
}

/// Runs [body] and returns its result, or the [Failure] for what it threw.
Future<Either<Failure, T>> guard<T>(Future<T> Function() body) async {
  try {
    return Right(await body());
  } catch (error) {
    return Left(failureFrom(error));
  }
}

/// Wraps each value of [source] in [Right] and turns its errors into [Left]
/// values, so one failed fetch does not end the stream.
Stream<Either<Failure, T>> guardStream<T>(Stream<T> source) {
  return source.transform(
    StreamTransformer.fromHandlers(
      handleData: (data, sink) => sink.add(Right(data)),
      handleError: (error, _, sink) => sink.add(Left(failureFrom(error))),
    ),
  );
}
