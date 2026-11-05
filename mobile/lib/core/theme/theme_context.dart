import 'package:flutter/material.dart';
import 'package:mirsad/core/theme/mirsad_colors.dart';

/// Shortcuts to the current theme.
extension ThemeContext on BuildContext {
  ColorScheme get colors => Theme.of(this).colorScheme;

  TextTheme get textStyles => Theme.of(this).textTheme;

  MirsadColors get statusColors => Theme.of(this).extension<MirsadColors>()!;
}
