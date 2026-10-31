import 'dart:async';

import 'package:flutter/foundation.dart';

/// Notifies listeners on every event of [stream], so GoRouter re-runs its
/// redirect when the sign-in state changes.
class StreamListenable extends ChangeNotifier {
  StreamListenable(Stream<Object?> stream) {
    _subscription = stream.listen((_) => notifyListeners());
  }

  late final StreamSubscription<Object?> _subscription;

  @override
  void dispose() {
    unawaited(_subscription.cancel());
    super.dispose();
  }
}
