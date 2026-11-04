import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/domain/repositories/home_repository.dart';

class WatchOverview {
  const WatchOverview(this._repository);

  final HomeRepository _repository;

  Stream<Either<Failure, OverviewStats>> call() => _repository.watchOverview();
}
