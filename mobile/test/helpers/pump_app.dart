import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/app_theme.dart';
import 'package:mirsad/core/utils/clock.dart';

import 'fake_clock.dart';

extension PumpApp on WidgetTester {
  /// Pumps [widget] inside a MaterialApp with the app's theme, localizations
  /// and a fixed [clock].
  Future<void> pumpApp(
    Widget widget, {
    Locale locale = const Locale('en'),
    Clock? clock,
  }) {
    return pumpWidget(
      RepositoryProvider<Clock>.value(
        value: clock ?? FakeClock(testNow),
        child: MaterialApp(
          theme: AppTheme.light(),
          locale: locale,
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          home: widget,
        ),
      ),
    );
  }
}
