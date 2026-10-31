import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';
import 'package:mirsad/features/activity/data/repositories/activity_repository_impl.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/either.dart';
import '../../activity_fixtures.dart';
import '../../activity_mocks.dart';

void main() {
  late MockActivityDataSource source;
  late ActivityRepositoryImpl repository;

  setUp(() {
    source = MockActivityDataSource();
    repository = ActivityRepositoryImpl(source);
  });

  test('watchEvents maps models to entities', () async {
    when(() => source.watchEvents()).thenAnswer(
      (_) => Stream.value([ActivityEventModel.fromJson(eventJson())]),
    );

    final result = await repository.watchEvents().first;

    expect(rightOf(result).single.tool, 'update_beneficiary');
  });

  test('watchEvents turns a stream error into a Left', () async {
    when(
      () => source.watchEvents(),
    ).thenAnswer((_) => Stream.error(const NetworkException()));

    expect(
      await repository.watchEvents().first,
      const Left<Failure, List<ActivityEvent>>(NetworkFailure()),
    );
  });

  test('refresh returns unit on success', () async {
    when(() => source.refresh()).thenAnswer((_) async {});
    expect(await repository.refresh(), const Right<Failure, Unit>(unit));
  });

  test('refresh returns the failure instead of throwing', () async {
    when(() => source.refresh()).thenThrow(const UnauthorizedException());
    expect(
      await repository.refresh(),
      const Left<Failure, Unit>(UnauthorizedFailure()),
    );
  });
}
