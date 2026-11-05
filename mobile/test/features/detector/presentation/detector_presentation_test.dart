import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/detector/presentation/cubit/detector_cubit.dart';
import 'package:mirsad/features/detector/presentation/pages/detector_page.dart';
import 'package:mocktail/mocktail.dart';

import '../../../helpers/pump_app.dart';
import '../detector_mocks.dart';

void main() {
  group('DetectorCubit', () {
    late MockScanText scanText;

    setUp(() => scanText = MockScanText());

    DetectorCubit build() => DetectorCubit(scanText: scanText);

    blocTest<DetectorCubit, DetectorState>(
      'shows the result of a scan',
      setUp: () => when(
        () => scanText(sampleText),
      ).thenAnswer((_) async => const Right(flagged)),
      build: build,
      act: (cubit) => cubit.scan(sampleText),
      expect: () => const [
        DetectorState(status: DetectorStatus.scanning),
        DetectorState(status: DetectorStatus.done, result: flagged),
      ],
    );

    blocTest<DetectorCubit, DetectorState>(
      'shows why a scan failed',
      setUp: () => when(
        () => scanText(any()),
      ).thenAnswer((_) async => const Left(NetworkFailure())),
      build: build,
      act: (cubit) => cubit.scan(sampleText),
      expect: () => const [
        DetectorState(status: DetectorStatus.scanning),
        DetectorState(
          status: DetectorStatus.failure,
          failure: NetworkFailure(),
        ),
      ],
    );

    blocTest<DetectorCubit, DetectorState>(
      'keeps the last result while scanning again',
      setUp: () => when(
        () => scanText(any()),
      ).thenAnswer((_) async => const Right(flagged)),
      build: build,
      seed: () =>
          const DetectorState(status: DetectorStatus.done, result: flagged),
      act: (cubit) => cubit.scan(sampleText),
      expect: () => const [
        DetectorState(status: DetectorStatus.scanning, result: flagged),
        DetectorState(status: DetectorStatus.done, result: flagged),
      ],
    );

    blocTest<DetectorCubit, DetectorState>(
      'ignores blank text',
      build: build,
      act: (cubit) => cubit.scan('   '),
      expect: () => const <DetectorState>[],
      verify: (_) => verifyNever(() => scanText(any())),
    );
  });

  group('DetectorPage', () {
    late MockDetectorCubit cubit;

    setUp(() {
      cubit = MockDetectorCubit();
      when(() => cubit.scan(any())).thenAnswer((_) async {});
    });

    Future<void> pumpPage(WidgetTester tester, DetectorState state) {
      tester.view
        ..physicalSize = const Size(1080, 2600)
        ..devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      whenListen(
        cubit,
        const Stream<DetectorState>.empty(),
        initialState: state,
      );
      return tester.pumpApp(
        BlocProvider<DetectorCubit>.value(
          value: cubit,
          child: const DetectorPage(),
        ),
      );
    }

    testWidgets('scans what was typed', (tester) async {
      await pumpPage(tester, const DetectorState());
      final scan = find.widgetWithText(FilledButton, 'Scan');
      expect(tester.widget<FilledButton>(scan).onPressed, isNull);

      await tester.enterText(find.byType(TextField), sampleText);
      await tester.pump();
      await tester.tap(scan);

      verify(() => cubit.scan(sampleText)).called(1);
    });

    testWidgets('shows the verdict and the flagged passage', (tester) async {
      await pumpPage(
        tester,
        const DetectorState(status: DetectorStatus.done, result: flagged),
      );

      expect(find.text('Prompt injection'), findsOneWidget);
      expect(find.text('Score 0.83'), findsOneWidget);
      expect(find.text('English'), findsOneWidget);
      expect(find.text('zero_width_chars'), findsOneWidget);
      expect(find.text('SAMPLE-FLAGGED-TEXT'), findsOneWidget);
      expect(find.text('override_instructions'), findsOneWidget);
    });
  });
}
