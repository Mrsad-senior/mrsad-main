import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/home/data/datasources/home_data_source.dart';
import 'package:mirsad/features/home/domain/entities/overview_stats.dart';
import 'package:mirsad/features/home/domain/repositories/home_repository.dart';

class HomeRepositoryImpl implements HomeRepository {
  const HomeRepositoryImpl(this._source);

  final HomeDataSource _source;

  @override
  Stream<Either<Failure, OverviewStats>> watchOverview() {
    return guardStream(
      _source.watchOverview().map((model) => model.toEntity()),
    );
  }

  @override
  Future<Either<Failure, Unit>> refreshOverview() {
    return guard(() async {
      await _source.refresh();
      return unit;
    });
  }
}
