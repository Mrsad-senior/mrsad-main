/// Fixed sizes that are not spacing: icons, stripes, content widths.
abstract final class AppSizes {
  static const double iconXs = 14;
  static const double iconSm = 18;
  static const double iconMd = 24;
  static const double iconLg = 48;
  static const double iconXl = 72;

  /// Width of the colored stripe at the start of a status-coded tile.
  static const double accentStripe = 4;

  /// Forms and single-column content stop growing past this width.
  static const double maxContentWidth = 480;

  /// Minimum height of tappable buttons.
  static const double buttonHeight = 48;
}
