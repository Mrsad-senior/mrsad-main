import 'package:mirsad/core/utils/clock.dart';

/// A clock that only moves when told to.
class FakeClock implements Clock {
  FakeClock(this.current);

  DateTime current;

  @override
  DateTime now() => current;

  void advance(Duration duration) => current = current.add(duration);
}

/// The fixed "now" most tests use: 29 Oct 2026, 09:42 UTC.
final DateTime testNow = DateTime.utc(2026, 10, 29, 9, 42);
