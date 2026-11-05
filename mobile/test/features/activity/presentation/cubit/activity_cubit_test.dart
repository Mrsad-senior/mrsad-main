import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';
import 'package:mirsad/features/activity/presentation/cubit/activity_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../../activity_fixtures.dart';
import '../../activity_mocks.dart';

void main() {
  late MockWatchActivity watchActivity;
  late MockRefreshActivity refreshActivity;
  late StreamController<Either<Failure, List<ActivityEvent>>> results;

  final denied = activityEvent(id: 'denied');
  final allowed = activityEvent(
    id: 'allowed',
    decision: GatewayDecision.allowed,
  );
  final events = [denied, allowed];

  setUp(() {
    watchActivity = MockWatchActivity();
    refreshActivity = MockRefreshActivity();
    results = StreamController.broadcast();
    when(() => watchActivity()).thenAnswer((_) => results.stream);
  });

  tearDown(() => results.close());

  ActivityCubit build() => ActivityCubit(
    watchActivity: watchActivity,
    refreshActivity: refreshActivity,
  );

  final ready = ActivityState(status: ActivityStatus.ready, events: events);

  blocTest<ActivityCubit, ActivityState>(
    'shows the feed when it arrives',
    build: build,
    act: (cubit) {
      cubit.start();
      results.add(Right(events));
    },
    expect: () => [ready],
  );

  blocTest<ActivityCubit, ActivityState>(
    'shows an error when the first load fails',
    build: build,
    act: (cubit) {
      cubit.start();
      results.add(const Left(NetworkFailure()));
    },
    expect: () => const [
      ActivityState(status: ActivityStatus.failure, failure: NetworkFailure()),
    ],
  );

  blocTest<ActivityCubit, ActivityState>(
    'filters by decision and keeps the filter when new events arrive',
    build: build,
    seed: () => ready,
    act: (cubit) {
      cubit
        ..start()
        ..setFilter(GatewayDecision.denied);
      results.add(Right([...events, activityEvent(id: 'new')]));
    },
    expect: () => [
      ActivityState(
        status: ActivityStatus.ready,
        events: events,
        filter: GatewayDecision.denied,
      ),
      ActivityState(
        status: ActivityStatus.ready,
        events: [
          ...events,
          activityEvent(id: 'new'),
        ],
        filter: GatewayDecision.denied,
      ),
    ],
    verify: (cubit) =>
        expect(cubit.state.visibleEvents.map((e) => e.id), ['denied', 'new']),
  );

  blocTest<ActivityCubit, ActivityState>(
    'reports a failed refresh without dropping the feed',
    setUp: () => when(
      () => refreshActivity(),
    ).thenAnswer((_) async => const Left(ServerFailure())),
    build: build,
    seed: () => ready,
    act: (cubit) => cubit.refresh(),
    expect: () => [
      ActivityState(
        status: ActivityStatus.ready,
        events: events,
        failure: const ServerFailure(),
      ),
    ],
  );

  test('counts events per decision', () {
    expect(ready.countOf(GatewayDecision.denied), 1);
    expect(ready.countOf(GatewayDecision.held), 0);
  });
}
