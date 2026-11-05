part of 'auth_cubit.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

/// Whether a reviewer is signed in. The router redirects on this.
class AuthState extends Equatable {
  const AuthState.unknown() : this._(AuthStatus.unknown);

  const AuthState.unauthenticated() : this._(AuthStatus.unauthenticated);

  const AuthState.authenticated(Reviewer reviewer)
    : this._(AuthStatus.authenticated, reviewer);

  const AuthState._(this.status, [this.reviewer]);

  final AuthStatus status;
  final Reviewer? reviewer;

  @override
  List<Object?> get props => [status, reviewer];
}
