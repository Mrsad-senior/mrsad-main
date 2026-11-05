import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/activity/domain/repositories/activity_repository.dart';

/// Re-fetches the activity feed, e.g. on pull-to-refresh.
class RefreshActivity {
  const RefreshActivity(this._repository);

  final ActivityRepository _repository;

  Future<Either<Failure, Unit>> call() => _repository.refresh();
}
