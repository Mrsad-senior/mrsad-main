part of 'sign_in_cubit.dart';

enum SignInStatus { idle, submitting, succeeded, failure }

class SignInState extends Equatable {
  const SignInState({this.status = SignInStatus.idle, this.failure});

  final SignInStatus status;

  /// Why the last attempt failed.
  final Failure? failure;

  bool get isSubmitting => status == SignInStatus.submitting;

  @override
  List<Object?> get props => [status, failure];
}
