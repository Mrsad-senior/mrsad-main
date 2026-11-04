import 'package:dio/dio.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/dio_error_mapping.dart';
import 'package:mirsad/features/detector/data/datasources/detector_data_source.dart';
import 'package:mirsad/features/detector/data/models/detection_result_model.dart';

/// `POST /api/detector/scan` ("Detector playground" in docs/api.md), which
/// every role may call. It only scores the text; nothing is audited or
/// blocked.
class DetectorApiDataSource implements DetectorDataSource {
  const DetectorApiDataSource(this._dio);

  static const path = '/api/detector/scan';

  final Dio _dio;

  @override
  Future<DetectionResultModel> scan(String text) {
    return callGateway(() async {
      final response = await _dio.post<Map<String, dynamic>>(
        path,
        data: {'text': text},
      );
      return DetectionResultModel.fromJson(
        response.data ??
            (throw const DataFormatException('Empty detector response')),
      );
    });
  }
}
