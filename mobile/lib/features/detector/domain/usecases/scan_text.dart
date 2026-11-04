import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';
import 'package:mirsad/features/detector/domain/repositories/detector_repository.dart';

class ScanText {
  const ScanText(this._repository);

  /// The gateway's limit (`MAX_SCAN_CHARS`).
  static const maxLength = 100000;

  final DetectorRepository _repository;

  /// Sends [text] as typed: spacing and invisible characters are part of
  /// what the detector looks at.
  Future<Either<Failure, DetectionResult>> call(String text) =>
      _repository.scan(text);
}
