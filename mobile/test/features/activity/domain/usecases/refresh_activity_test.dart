import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/usecases/refresh_activity.dart';
import 'package:mocktail/mocktail.dart';

import '../../activity_mocks.dart';

void main() {
  late MockActivityRepository repository;

  setUp(() => repository = MockActivityRepository());

  test('asks the repository to refresh', () async {
    when(() => repository.refresh()).thenAnswer((_) async => const Right(unit));

    expect(
      await RefreshActivity(repository)(),
      const Right<Failure, Unit>(unit),
    );
    verify(() => repository.refresh()).called(1);
  });

  test('returns the repository failure', () async {
    when(
      () => repository.refresh(),
    ).thenAnswer((_) async => const Left(UnauthorizedFailure()));

    expect(
      await RefreshActivity(repository)(),
      const Left<Failure, Unit>(UnauthorizedFailure()),
    );
  });
}
