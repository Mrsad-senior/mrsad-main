import 'dart:async';

import 'package:mirsad/core/utils/clock.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/data/datasources/mock/demo_events.dart';
import 'package:mirsad/features/activity/data/models/activity_event_model.dart';

/// The finance demo's activity feed, in memory.
class ActivityMockDataSource implements ActivityDataSource {
  ActivityMockDataSource({
    required Clock clock,
    this.latency = const Duration(milliseconds: 400),
  }) : _events = demoEvents(clock.now());

  /// Simulated network delay.
  final Duration latency;

  final List<ActivityEventModel> _events;
  final StreamController<void> _changes = StreamController.broadcast();

  @override
  Stream<List<ActivityEventModel>> watchEvents() async* {
    await Future<void>.delayed(latency);
    yield List.unmodifiable(_events);
    yield* _changes.stream.map((_) => List.unmodifiable(_events));
  }

  @override
  Future<void> refresh() async {
    await Future<void>.delayed(latency);
    _changes.add(null);
  }

  Future<void> dispose() => _changes.close();
}
