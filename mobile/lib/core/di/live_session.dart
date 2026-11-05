import 'dart:async';

import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// Keeps the gateway's live stream open while someone is signed in: it
/// needs their token, and signing out (or in as someone else) must close it.
StreamSubscription<AuthState> connectLiveUpdatesToSession({
  required AuthCubit auth,
  required LiveUpdates live,
}) {
  void follow(AuthState state) {
    if (state.status == AuthStatus.authenticated) {
      live.start();
    } else {
      unawaited(live.stop());
    }
  }

  follow(auth.state);
  return auth.stream.listen(follow);
}
