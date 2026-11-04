import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/domain/usecases/refresh_overview.dart';
import 'package:mirsad/features/home/domain/usecases/watch_overview.dart';
import 'package:mocktail/mocktail.dart';

import '../../home_fixtures.dart';
import '../../home_mocks.dart';

void main() {
  late MockHomeRepository repository;

  setUp(() => repository = MockHomeRepository());

  test('WatchOverview follows the repository', () async {
    when(() => repository.watchOverview()).thenAnswer(
      (_) => Stream.value(const Right<Failure, OverviewStats>(overviewStats)),
    );
    expect(
      await WatchOverview(repository)().first,
      const Right<Failure, OverviewStats>(overviewStats),
    );
  });

  test('RefreshOverview asks the repository', () async {
    when(
      () => repository.refreshOverview(),
    ).thenAnswer((_) async => const Right(unit));
    expect(
      await RefreshOverview(repository)(),
      const Right<Failure, Unit>(unit),
    );
    verify(() => repository.refreshOverview()).called(1);
  });
}
