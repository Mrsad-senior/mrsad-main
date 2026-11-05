import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';

abstract interface class HomeRepository {
  /// Emits the overview now and whenever the gateway reports new activity.
  /// A failed fetch arrives as a [Left] and the stream carries on.
  Stream<Either<Failure, OverviewStats>> watchOverview();

  /// Fetches the overview again and pushes it to [watchOverview].
  Future<Either<Failure, Unit>> refreshOverview();
}
