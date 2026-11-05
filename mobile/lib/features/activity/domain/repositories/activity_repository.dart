import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';

abstract interface class ActivityRepository {
  /// The latest gateway decisions, re-emitted whenever new ones arrive. A
  /// failed update arrives as a [Left] and the stream stays open.
  Stream<Either<Failure, List<ActivityEvent>>> watchEvents();

  /// Fetches the feed again now; the result arrives on [watchEvents].
  Future<Either<Failure, Unit>> refresh();
}
