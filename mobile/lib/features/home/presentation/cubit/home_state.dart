part of 'home_cubit.dart';

enum HomeStatus { loading, ready, failure }

class HomeState extends Equatable {
  const HomeState({this.status = HomeStatus.loading, this.stats, this.failure});

  final HomeStatus status;

  /// The latest overview.
  final OverviewStats? stats;

  /// The latest failure. With [HomeStatus.ready] the figures stay on screen
  /// and the failure is reported in a snackbar.
  final Failure? failure;

  @override
  List<Object?> get props => [status, stats, failure];
}
