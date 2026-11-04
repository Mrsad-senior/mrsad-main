import 'package:mirsad/features/detector/data/models/detection_result_model.dart';

/// The detector playground. Implemented by the mock and API sources. Throws
/// `AppException`s.
abstract interface class DetectorDataSource {
  Future<DetectionResultModel> scan(String text);
}
