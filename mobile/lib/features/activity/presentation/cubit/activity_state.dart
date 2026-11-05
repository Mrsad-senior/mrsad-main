part of 'activity_cubit.dart';

enum ActivityStatus { loading, ready, failure }

class ActivityState extends Equatable {
  const ActivityState({
    this.status = ActivityStatus.loading,
    this.events = const [],
    this.filter,
    this.failure,
  });

  final ActivityStatus status;

  /// Every event, newest first.
  final List<ActivityEvent> events;

  /// Only events with this decision are shown. Null shows all of them.
  final GatewayDecision? filter;

  /// The latest failure. With [ActivityStatus.ready] the feed stays on
  /// screen and the failure is reported in a snackbar.
  final Failure? failure;

  List<ActivityEvent> get visibleEvents {
    final selected = filter;
    if (selected == null) return events;
    return events.where((event) => event.decision == selected).toList();
  }

  int countOf(GatewayDecision decision) =>
      events.where((event) => event.decision == decision).length;

  @override
  List<Object?> get props => [status, events, filter, failure];
}
