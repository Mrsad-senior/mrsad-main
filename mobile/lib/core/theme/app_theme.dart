import 'package:flutter/material.dart';
import 'package:mirsad/core/theme/mirsad_colors.dart';
import 'package:mirsad/core/theme/tokens/app_colors.dart';
import 'package:mirsad/core/theme/tokens/app_radii.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_typography.dart';

/// Builds the light and dark themes from the design tokens.
abstract final class AppTheme {
  static ThemeData light() =>
      _build(AppColors.lightScheme, AppColors.lightStatus);

  static ThemeData dark() => _build(AppColors.darkScheme, AppColors.darkStatus);

  static ThemeData _build(ColorScheme scheme, MirsadColors status) {
    return ThemeData(
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      // Null until the Figma font is added; kept so swapping it is one line.
      // ignore: avoid_redundant_argument_values
      fontFamily: AppTypography.fontFamily,
      textTheme: AppTypography.textTheme,
      extensions: [status],
      appBarTheme: AppBarThemeData(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 1,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: scheme.surfaceContainerLowest,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: AppRadii.card,
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      inputDecorationTheme: const InputDecorationThemeData(
        border: OutlineInputBorder(borderRadius: AppRadii.input),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(AppSizes.buttonHeight, AppSizes.buttonHeight),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.input),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(AppSizes.buttonHeight, AppSizes.buttonHeight),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.input),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: scheme.surfaceContainer,
        indicatorColor: scheme.primaryContainer,
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
      dividerTheme: DividerThemeData(color: scheme.outlineVariant, space: 1),
    );
  }
}
