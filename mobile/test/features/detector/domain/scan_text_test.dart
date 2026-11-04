import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';
import 'package:mirsad/features/detector/domain/usecases/scan_text.dart';
import 'package:mocktail/mocktail.dart';

import '../detector_mocks.dart';

void main() {
  test('sends the text exactly as typed', () async {
    final repository = MockDetectorRepository();
    const typed = '  spaced\u200b text  ';
    when(
      () => repository.scan(typed),
    ).thenAnswer((_) async => const Right(flagged));

    expect(
      await ScanText(repository)(typed),
      const Right<Failure, DetectionResult>(flagged),
    );
    verify(() => repository.scan(typed)).called(1);
  });

  test('knows the gateway limit', () {
    expect(ScanText.maxLength, 100000);
  });
}
