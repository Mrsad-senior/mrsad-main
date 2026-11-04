import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/home/domain/repositories/home_repository.dart';

class RefreshOverview {
  const RefreshOverview(this._repository);

  final HomeRepository _repository;

  Future<Either<Failure, Unit>> call() => _repository.refreshOverview();
}
