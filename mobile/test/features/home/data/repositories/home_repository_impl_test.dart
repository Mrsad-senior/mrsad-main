import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/data/models/overview_stats_model.dart';
import 'package:mirsad/features/home/data/repositories/home_repository_impl.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mocktail/mocktail.dart';

import '../../home_fixtures.dart';
import '../../home_mocks.dart';

void main() {
  late MockHomeDataSource source;
  late HomeRepositoryImpl repository;

  setUp(() {
    source = MockHomeDataSource();
    repository = HomeRepositoryImpl(source);
  });

  test('maps models to entities and errors to failures', () async {
    when(() => source.watchOverview()).thenAnswer(
      (_) => Stream.fromIterable([
        OverviewStatsModel.fromJson(overviewJson()),
      ]).followedBy(Stream.error(const NetworkException())),
    );

    expect(await repository.watchOverview().toList(), const [
      Right<Failure, OverviewStats>(overviewStats),
      Left<Failure, OverviewStats>(NetworkFailure()),
    ]);
  });

  test('refresh reports a failure instead of throwing', () async {
    when(() => source.refresh()).thenThrow(const UnauthorizedException());
    expect(
      await repository.refreshOverview(),
      const Left<Failure, Unit>(UnauthorizedFailure()),
    );
  });
}

extension<T> on Stream<T> {
  Stream<T> followedBy(Stream<T> next) async* {
    yield* this;
    yield* next;
  }
}
