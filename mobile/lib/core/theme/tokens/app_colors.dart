import 'package:flutter/material.dart';
import 'package:mirsad/core/theme/mirsad_colors.dart';

/// Every color value in the app. Replace these with the Figma color styles;
/// widgets only reach them through the theme.
abstract final class AppColors {
  static const ColorScheme lightScheme = ColorScheme(
    brightness: Brightness.light,
    primary: Color(0xFF0F4C5C),
    onPrimary: Color(0xFFFFFFFF),
    primaryContainer: Color(0xFFCDE8EE),
    onPrimaryContainer: Color(0xFF00222B),
    secondary: Color(0xFF4A6268),
    onSecondary: Color(0xFFFFFFFF),
    secondaryContainer: Color(0xFFCDE7EE),
    onSecondaryContainer: Color(0xFF051F24),
    error: Color(0xFFB3261E),
    onError: Color(0xFFFFFFFF),
    errorContainer: Color(0xFFF9DEDC),
    onErrorContainer: Color(0xFF410E0B),
    surface: Color(0xFFF7FAFB),
    onSurface: Color(0xFF161D1F),
    onSurfaceVariant: Color(0xFF3F484B),
    surfaceContainerLowest: Color(0xFFFFFFFF),
    surfaceContainerLow: Color(0xFFF1F5F6),
    surfaceContainer: Color(0xFFEBF0F1),
    surfaceContainerHigh: Color(0xFFE5EAEB),
    surfaceContainerHighest: Color(0xFFDFE4E5),
    outline: Color(0xFF6F797B),
    outlineVariant: Color(0xFFBFC8CB),
    inverseSurface: Color(0xFF2B3133),
    onInverseSurface: Color(0xFFECF2F3),
    inversePrimary: Color(0xFF8AD0E2),
  );

  static const ColorScheme darkScheme = ColorScheme(
    brightness: Brightness.dark,
    primary: Color(0xFF8AD0E2),
    onPrimary: Color(0xFF00363F),
    primaryContainer: Color(0xFF004E5B),
    onPrimaryContainer: Color(0xFFCDE8EE),
    secondary: Color(0xFFB1CBD2),
    onSecondary: Color(0xFF1C3439),
    secondaryContainer: Color(0xFF334A50),
    onSecondaryContainer: Color(0xFFCDE7EE),
    error: Color(0xFFF2B8B5),
    onError: Color(0xFF601410),
    errorContainer: Color(0xFF8C1D18),
    onErrorContainer: Color(0xFFF9DEDC),
    surface: Color(0xFF0F1416),
    onSurface: Color(0xFFDEE3E5),
    onSurfaceVariant: Color(0xFFBFC8CB),
    surfaceContainerLowest: Color(0xFF0A0F10),
    surfaceContainerLow: Color(0xFF171D1E),
    surfaceContainer: Color(0xFF1B2122),
    surfaceContainerHigh: Color(0xFF252B2D),
    surfaceContainerHighest: Color(0xFF303638),
    outline: Color(0xFF899295),
    outlineVariant: Color(0xFF3F484B),
    inverseSurface: Color(0xFFDEE3E5),
    onInverseSurface: Color(0xFF2B3133),
    inversePrimary: Color(0xFF0F4C5C),
  );

  static const MirsadColors lightStatus = MirsadColors(
    allowed: StatusColors(
      foreground: Color(0xFF1E7D4F),
      container: Color(0xFFD9F2E3),
      onContainer: Color(0xFF0B3D25),
    ),
    denied: StatusColors(
      foreground: Color(0xFFB3261E),
      container: Color(0xFFF9DEDC),
      onContainer: Color(0xFF5C1410),
    ),
    held: StatusColors(
      foreground: Color(0xFFA15C00),
      container: Color(0xFFFFE6C2),
      onContainer: Color(0xFF4D2C00),
    ),
    neutral: StatusColors(
      foreground: Color(0xFF5E6670),
      container: Color(0xFFE6E9ED),
      onContainer: Color(0xFF2B3036),
    ),
  );

  static const MirsadColors darkStatus = MirsadColors(
    allowed: StatusColors(
      foreground: Color(0xFF6FD39C),
      container: Color(0xFF123A27),
      onContainer: Color(0xFFBFF0D3),
    ),
    denied: StatusColors(
      foreground: Color(0xFFF2B8B5),
      container: Color(0xFF4F1A17),
      onContainer: Color(0xFFFFDAD6),
    ),
    held: StatusColors(
      foreground: Color(0xFFF5B95F),
      container: Color(0xFF412A06),
      onContainer: Color(0xFFFFDDB0),
    ),
    neutral: StatusColors(
      foreground: Color(0xFFA9B1BA),
      container: Color(0xFF2A3038),
      onContainer: Color(0xFFDDE2E8),
    ),
  );
}
