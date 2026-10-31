import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/repositories/activity_repository.dart';

/// The activity feed, newest first.
class WatchActivity {
  const WatchActivity(this._repository);

  final ActivityRepository _repository;

  Stream<Either<Failure, List<ActivityEvent>>> call() {
    return _repository.watchEvents().map(
      (result) => result.map(
        (events) =>
            [...events]..sort((a, b) => b.createdAt.compareTo(a.createdAt)),
      ),
    );
  }
}
