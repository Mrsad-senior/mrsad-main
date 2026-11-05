import 'dart:ui';

import 'package:flutter_bloc/flutter_bloc.dart';

/// The language the reviewer picked. Null follows the device language.
class LocaleCubit extends Cubit<Locale?> {
  LocaleCubit() : super(null);

  static const english = Locale('en');
  static const arabic = Locale('ar');

  void setLocale(Locale? locale) => emit(locale);

  /// Switches between English and Arabic, starting from [current], the
  /// language on screen now.
  void toggle(Locale current) {
    emit(current.languageCode == arabic.languageCode ? english : arabic);
  }
}
