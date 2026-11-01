/// The gateway sends timestamps as UNIX epoch seconds, usually with a
/// fraction (e.g. `1761731467.25`). For `@JsonKey(fromJson: ...)`.
DateTime dateTimeFromEpochSeconds(num seconds) {
  return DateTime.fromMicrosecondsSinceEpoch(
    (seconds * Duration.microsecondsPerSecond).round(),
    isUtc: true,
  );
}
