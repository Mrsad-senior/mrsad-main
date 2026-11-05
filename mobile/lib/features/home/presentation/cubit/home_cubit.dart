import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/domain/usecases/refresh_overview.dart';
import 'package:mirsad/features/home/domain/usecases/watch_overview.dart';

part 'home_state.dart';

class HomeCubit extends Cubit<HomeState> {
  HomeCubit({required this._watchOverview, required this._refreshOverview})
    : super(const HomeState());

  final WatchOverview _watchOverview;
  final RefreshOverview _refreshOverview;
  StreamSubscription<Either<Failure, OverviewStats>>? _subscription;

  /// Starts following the overview. Calling it again does nothing.
  void start() {
    _subscription ??= _watchOverview().listen(
      (result) => result.match(_onFailure, _onStats),
    );
  }

  /// Pull-to-refresh. The new figures arrive through the subscription.
  Future<void> refresh() async {
    final result = await _refreshOverview();
    result.match(_onFailure, (_) {});
  }

  /// Starts over after the first load failed.
  Future<void> retry() async {
    await _subscription?.cancel();
    _subscription = null;
    emit(const HomeState());
    start();
  }

  void _onStats(OverviewStats stats) {
    emit(HomeState(status: HomeStatus.ready, stats: stats));
  }

  void _onFailure(Failure failure) {
    final hadStats = state.status == HomeStatus.ready;
    emit(
      HomeState(
        status: hadStats ? HomeStatus.ready : HomeStatus.failure,
        stats: state.stats,
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
