import 'package:bloc_test/bloc_test.dart';
import 'package:mirsad/features/detector/data/datasources/detector_data_source.dart';
import 'package:mirsad/features/detector/domain/entities/detection_label.dart';
import 'package:mirsad/features/detector/domain/entities/detection_language.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';
import 'package:mirsad/features/detector/domain/entities/detection_span.dart';
import 'package:mirsad/features/detector/domain/repositories/detector_repository.dart';
import 'package:mirsad/features/detector/domain/usecases/scan_text.dart';
import 'package:mirsad/features/detector/presentation/cubit/detector_cubit.dart';
import 'package:mocktail/mocktail.dart';

class MockDetectorRepository extends Mock implements DetectorRepository {}

class MockDetectorDataSource extends Mock implements DetectorDataSource {}

class MockScanText extends Mock implements ScanText {}

class MockDetectorCubit extends MockCubit<DetectorState>
    implements DetectorCubit {}

/// A neutral placeholder, like the gateway's own tests use: no attack text.
const sampleText = 'Please process invoice INV-2026-0419. SAMPLE-FLAGGED-TEXT';

const flagged = DetectionResult(
  score: 0.83,
  label: DetectionLabel.injection,
  language: DetectionLanguage.en,
  spans: [
    DetectionSpan(
      start: 38,
      end: 57,
      text: 'SAMPLE-FLAGGED-TEXT',
      ruleId: 'override_instructions',
    ),
  ],
  signals: ['zero_width_chars'],
);

/// `POST /api/detector/scan` for [flagged], shaped like `DetectionResult`.
Map<String, dynamic> flaggedJson() => {
  'score': 0.83,
  'label': 'injection',
  'language': 'en',
  'spans': [
    {
      'start': 38,
      'end': 57,
      'text': 'SAMPLE-FLAGGED-TEXT',
      'rule_id': 'override_instructions',
      'score': 1.0,
    },
  ],
  'signals': ['zero_width_chars'],
  'model_score': 0.7,
  'rule_score': 0.9,
  'layer_scores': <String, dynamic>{},
  'layer_reasons': <String, dynamic>{},
  'latency_ms': 3.1,
};
