import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/usecases/watch_activity.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/either.dart';
import '../../activity_fixtures.dart';
import '../../activity_mocks.dart';

void main() {
  late MockActivityRepository repository;

  setUp(() => repository = MockActivityRepository());

  test('puts the newest event first', () async {
    final older = activityEvent(id: 'older', age: const Duration(hours: 1));
    final newer = activityEvent(id: 'newer');
    when(
      () => repository.watchEvents(),
    ).thenAnswer((_) => Stream.value(Right([older, newer])));

    final result = await WatchActivity(repository)().first;

    expect(rightOf(result).map((e) => e.id), ['newer', 'older']);
  });

  test('passes failures through', () async {
    const failure = Left<Failure, List<ActivityEvent>>(NetworkFailure());
    when(
      () => repository.watchEvents(),
    ).thenAnswer((_) => Stream.value(failure));

    expect(await WatchActivity(repository)().first, failure);
  });
}
