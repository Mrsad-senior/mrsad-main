import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';
import 'package:mirsad/features/detector/domain/usecases/scan_text.dart';

part 'detector_state.dart';

class DetectorCubit extends Cubit<DetectorState> {
  DetectorCubit({required this._scanText}) : super(const DetectorState());

  final ScanText _scanText;

  /// Scans [text]. Blank text, or a second tap while scanning, does nothing.
  /// The previous result stays visible while the new scan runs.
  Future<void> scan(String text) async {
    if (text.trim().isEmpty || state.status == DetectorStatus.scanning) return;
    emit(DetectorState(status: DetectorStatus.scanning, result: state.result));
    final outcome = await _scanText(text);
    emit(
      outcome.match(
        (failure) =>
            DetectorState(status: DetectorStatus.failure, failure: failure),
        (result) => DetectorState(status: DetectorStatus.done, result: result),
      ),
    );
  }
}
