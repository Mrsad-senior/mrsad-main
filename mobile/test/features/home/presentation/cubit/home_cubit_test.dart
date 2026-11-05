import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/presentation/cubit/home_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../../home_fixtures.dart';
import '../../home_mocks.dart';

void main() {
  late MockWatchOverview watchOverview;
  late MockRefreshOverview refreshOverview;

  setUp(() {
    watchOverview = MockWatchOverview();
    refreshOverview = MockRefreshOverview();
  });

  HomeCubit build() =>
      HomeCubit(watchOverview: watchOverview, refreshOverview: refreshOverview);

  void stream(List<Either<Failure, OverviewStats>> results) {
    when(() => watchOverview()).thenAnswer((_) => Stream.fromIterable(results));
  }

  blocTest<HomeCubit, HomeState>(
    'shows the overview',
    setUp: () => stream([const Right(overviewStats)]),
    build: build,
    act: (cubit) => cubit.start(),
    expect: () => const [
      HomeState(status: HomeStatus.ready, stats: overviewStats),
    ],
  );

  blocTest<HomeCubit, HomeState>(
    'shows an error when the first load fails',
    setUp: () => stream([const Left(NetworkFailure())]),
    build: build,
    act: (cubit) => cubit.start(),
    expect: () => const [
      HomeState(status: HomeStatus.failure, failure: NetworkFailure()),
    ],
  );

  blocTest<HomeCubit, HomeState>(
    'keeps the figures on screen when a later fetch fails',
    setUp: () =>
        stream([const Right(overviewStats), const Left(NetworkFailure())]),
    build: build,
    act: (cubit) => cubit.start(),
    expect: () => const [
      HomeState(status: HomeStatus.ready, stats: overviewStats),
      HomeState(
        status: HomeStatus.ready,
        stats: overviewStats,
        failure: NetworkFailure(),
      ),
    ],
  );

  blocTest<HomeCubit, HomeState>(
    'reports a failed pull-to-refresh',
    setUp: () => when(
      () => refreshOverview(),
    ).thenAnswer((_) async => const Left(ServerFailure())),
    build: build,
    seed: () => const HomeState(status: HomeStatus.ready, stats: overviewStats),
    act: (cubit) => cubit.refresh(),
    expect: () => const [
      HomeState(
        status: HomeStatus.ready,
        stats: overviewStats,
        failure: ServerFailure(),
      ),
    ],
  );
}
