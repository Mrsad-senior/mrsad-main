part of 'detector_cubit.dart';

enum DetectorStatus { idle, scanning, done, failure }

class DetectorState extends Equatable {
  const DetectorState({
    this.status = DetectorStatus.idle,
    this.result,
    this.failure,
  });

  final DetectorStatus status;

  /// The latest result; kept while a new scan runs.
  final DetectionResult? result;

  final Failure? failure;

  @override
  List<Object?> get props => [status, result, failure];
}
