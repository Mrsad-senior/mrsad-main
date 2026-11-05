import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';

/// The value inside a [Right], failing the test on a [Left].
T rightOf<T>(Either<Failure, T> result) {
  return result.match(
    (failure) => fail('Expected Right, got Left($failure)'),
    (value) => value,
  );
}
