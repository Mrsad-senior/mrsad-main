import 'dart:ui';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/l10n/locale_cubit.dart';

void main() {
  test('starts by following the device language', () {
    expect(LocaleCubit().state, isNull);
  });

  blocTest<LocaleCubit, Locale?>(
    'toggle switches English to Arabic',
    build: LocaleCubit.new,
    act: (cubit) => cubit.toggle(const Locale('en')),
    expect: () => [LocaleCubit.arabic],
  );

  blocTest<LocaleCubit, Locale?>(
    'toggle switches Arabic to English',
    build: LocaleCubit.new,
    act: (cubit) => cubit.toggle(const Locale('ar', 'SA')),
    expect: () => [LocaleCubit.english],
  );
}
