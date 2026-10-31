import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/activity/data/datasources/activity_data_source.dart';
import 'package:mirsad/features/activity/domain/entities/activity_event.dart';
import 'package:mirsad/features/activity/domain/repositories/activity_repository.dart';

class ActivityRepositoryImpl implements ActivityRepository {
  ActivityRepositoryImpl(this._source);

  final ActivityDataSource _source;

  @override
  Stream<Either<Failure, List<ActivityEvent>>> watchEvents() {
    return guardStream(
      _source.watchEvents().map(
        (models) => [for (final model in models) model.toEntity()],
      ),
    );
  }

  @override
  Future<Either<Failure, Unit>> refresh() {
    return guard(() async {
      await _source.refresh();
      return unit;
    });
  }
}
