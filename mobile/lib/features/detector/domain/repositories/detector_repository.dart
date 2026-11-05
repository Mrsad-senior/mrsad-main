import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';

abstract interface class DetectorRepository {
  /// Runs [text] through the gateway's detector, as it would a tool result.
  Future<Either<Failure, DetectionResult>> scan(String text);
}
