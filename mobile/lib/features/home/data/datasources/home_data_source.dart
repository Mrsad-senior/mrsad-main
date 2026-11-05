import 'package:mirsad/features/home/data/models/overview_stats_model.dart';

/// The home overview. Implemented by the mock and API sources. Methods
/// throw `AppException`s on failure.
abstract interface class HomeDataSource {
  /// Emits the overview now and whenever it may have changed. Errors arrive
  /// as stream errors and do not end the stream.
  Stream<OverviewStatsModel> watchOverview();

  /// Fetches the overview again and pushes it to [watchOverview].
  Future<void> refresh();
}
