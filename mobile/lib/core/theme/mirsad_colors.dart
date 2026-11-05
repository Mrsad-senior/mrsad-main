import 'package:flutter/material.dart';

/// The colors for one status: allowed, denied, held or neutral.
@immutable
class StatusColors {
  const StatusColors({
    required this.foreground,
    required this.container,
    required this.onContainer,
  });

  /// Icons and accent stripes on a normal surface.
  final Color foreground;

  /// Badge and banner backgrounds.
  final Color container;

  /// Text and icons on [container].
  final Color onContainer;

  static StatusColors lerp(StatusColors a, StatusColors b, double t) {
    return StatusColors(
      foreground: Color.lerp(a.foreground, b.foreground, t)!,
      container: Color.lerp(a.container, b.container, t)!,
      onContainer: Color.lerp(a.onContainer, b.onContainer, t)!,
    );
  }
}

/// Mirsad's status colors, which Material's [ColorScheme] has no slots for.
///
/// Read them with `context.statusColors`. The values live in
/// `tokens/app_colors.dart`.
@immutable
class MirsadColors extends ThemeExtension<MirsadColors> {
  const MirsadColors({
    required this.allowed,
    required this.denied,
    required this.held,
    required this.neutral,
  });

  final StatusColors allowed;
  final StatusColors denied;
  final StatusColors held;

  /// Expired items and other states with no verdict.
  final StatusColors neutral;

  @override
  MirsadColors copyWith({
    StatusColors? allowed,
    StatusColors? denied,
    StatusColors? held,
    StatusColors? neutral,
  }) {
    return MirsadColors(
      allowed: allowed ?? this.allowed,
      denied: denied ?? this.denied,
      held: held ?? this.held,
      neutral: neutral ?? this.neutral,
    );
  }

  @override
  MirsadColors lerp(MirsadColors? other, double t) {
    if (other == null) return this;
    return MirsadColors(
      allowed: StatusColors.lerp(allowed, other.allowed, t),
      denied: StatusColors.lerp(denied, other.denied, t),
      held: StatusColors.lerp(held, other.held, t),
      neutral: StatusColors.lerp(neutral, other.neutral, t),
    );
  }
}
