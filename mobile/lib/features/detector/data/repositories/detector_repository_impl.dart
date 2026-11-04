import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/detector/data/datasources/detector_data_source.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';
import 'package:mirsad/features/detector/domain/repositories/detector_repository.dart';

class DetectorRepositoryImpl implements DetectorRepository {
  const DetectorRepositoryImpl(this._source);

  final DetectorDataSource _source;

  @override
  Future<Either<Failure, DetectionResult>> scan(String text) {
    return guard(() async => (await _source.scan(text)).toEntity());
  }
}
