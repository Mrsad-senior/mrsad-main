/// Source of the current time. Inject it instead of calling `DateTime.now()`
/// so countdowns and mock data can be tested.
abstract interface class Clock {
  DateTime now();
}

class SystemClock implements Clock {
  const SystemClock();

  @override
  DateTime now() => DateTime.now();
}
