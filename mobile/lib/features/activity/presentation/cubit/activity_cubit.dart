import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';
import 'package:mirsad/features/activity/domain/usecases/refresh_activity.dart';
import 'package:mirsad/features/activity/domain/usecases/watch_activity.dart';

part 'activity_state.dart';

class ActivityCubit extends Cubit<ActivityState> {
  ActivityCubit({required this._watchActivity, required this._refreshActivity})
    : super(const ActivityState());

  final WatchActivity _watchActivity;
  final RefreshActivity _refreshActivity;
  StreamSubscription<Either<Failure, List<ActivityEvent>>>? _subscription;

  /// Starts following the feed. Calling it again does nothing.
  void start() {
    _subscription ??= _watchActivity().listen(
      (result) => result.match(_onFailure, _onEvents),
    );
  }

  /// Pull-to-refresh. The new feed arrives through the subscription.
  Future<void> refresh() async {
    final result = await _refreshActivity();
    result.match(_onFailure, (_) {});
  }

  /// Starts over after the first load failed.
  Future<void> retry() async {
    await _subscription?.cancel();
    _subscription = null;
    emit(ActivityState(filter: state.filter));
    start();
  }

  /// Shows only events with [decision], or all of them for null.
  void setFilter(GatewayDecision? decision) {
    emit(
      ActivityState(
        status: state.status,
        events: state.events,
        filter: decision,
        failure: state.failure,
      ),
    );
  }

  void _onEvents(List<ActivityEvent> events) {
    emit(
      ActivityState(
        status: ActivityStatus.ready,
        events: events,
        filter: state.filter,
      ),
    );
  }

  void _onFailure(Failure failure) {
    final hadFeed = state.status == ActivityStatus.ready;
    emit(
      ActivityState(
        status: hadFeed ? ActivityStatus.ready : ActivityStatus.failure,
        events: state.events,
        filter: state.filter,
        failure: failure,
      ),
    );
  }

  @override
  Future<void> close() async {
    await _subscription?.cancel();
    return super.close();
  }
}
