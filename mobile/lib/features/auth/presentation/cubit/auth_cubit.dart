import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/usecases/get_current_reviewer.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_out.dart';
import 'package:mirsad/features/auth/domain/usecases/watch_reviewer.dart';

part 'auth_state.dart';

/// The app-wide sign-in state.
class AuthCubit extends Cubit<AuthState> {
  AuthCubit({
    required this._getCurrentReviewer,
    required this._watchReviewer,
    required this._signOut,
  }) : super(const AuthState.unknown());

  final GetCurrentReviewer _getCurrentReviewer;
  final WatchReviewer _watchReviewer;
  final SignOut _signOut;
  StreamSubscription<Reviewer?>? _subscription;

  /// Reads the current session right away, so the router knows where to go
  /// on launch, then follows changes. Calling it again does nothing.
  void start() {
    if (_subscription != null) return;
    _show(_getCurrentReviewer());
    _subscription = _watchReviewer().listen(_show);
  }

  /// The sign-out arrives through [start]'s subscription. If it fails the
  /// reviewer simply stays signed in.
  Future<void> signOut() async {
    await _signOut();
  }

  void _show(Reviewer? reviewer) {
    emit(
      reviewer == null
          ? const AuthState.unauthenticated()
          : AuthState.authenticated(reviewer),
    );
  }

  @override
  Future<void> close() async {
    await _subscription?.cancel();
    return super.close();
  }
}
