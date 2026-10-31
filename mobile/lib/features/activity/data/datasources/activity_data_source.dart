import 'package:mirsad/features/activity/data/models/activity_event_model.dart';

/// Reads the activity feed. Implemented by the mock, API and Supabase
/// sources. Methods throw `AppException`s on failure.
abstract interface class ActivityDataSource {
  /// Emits the latest events now and whenever new ones arrive. Errors arrive
  /// as stream errors and do not end the stream.
  Stream<List<ActivityEventModel>> watchEvents();

  /// Fetches the feed again and pushes it to [watchEvents].
  Future<void> refresh();
}
