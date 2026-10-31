import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';

void main() {
  group('failureFrom', () {
    final cases = <Object, Failure>{
      const NetworkException('offline'): const NetworkFailure('offline'),
      const ServerException(statusCode: 500, message: 'boom'):
          const ServerFailure(statusCode: 500, detail: 'boom'),
      const UnauthorizedException(): const UnauthorizedFailure(),
      const NotFoundException(): const NotFoundFailure(),
      const ConflictException(): const ConflictFailure(),
      const InvalidCredentialsException(): const InvalidCredentialsFailure(),
      const DataFormatException('bad'): const DataFormatFailure('bad'),
      const FormatException('bad date'): const DataFormatFailure('bad date'),
    };
    cases.forEach((error, failure) {
      test('maps ${error.runtimeType} to ${failure.runtimeType}', () {
        expect(failureFrom(error), failure);
      });
    });

    test('maps anything else to UnexpectedFailure', () {
      expect(failureFrom(StateError('oops')), isA<UnexpectedFailure>());
    });
  });

  group('guard', () {
    test('returns the value on success', () async {
      expect(await guard(() async => 42), const Right<Failure, int>(42));
    });

    test('returns the failure for a thrown exception', () async {
      final result = await guard<int>(
        () async => throw const NotFoundException(),
      );
      expect(result, const Left<Failure, int>(NotFoundFailure()));
    });
  });

  test('guardStream keeps the stream open after an error', () async {
    final controller = StreamController<int>();
    final expectation = expectLater(
      guardStream(controller.stream),
      emitsInOrder([
        const Right<Failure, int>(1),
        const Left<Failure, int>(NetworkFailure()),
        const Right<Failure, int>(2),
        emitsDone,
      ]),
    );
    controller
      ..add(1)
      ..addError(const NetworkException())
      ..add(2);
    await controller.close();
    await expectation;
  });
}
