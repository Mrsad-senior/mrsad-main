import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_in.dart';

part 'sign_in_state.dart';

/// The sign-in form. On success the router leaves the page by itself,
/// because `AuthCubit` sees the new session.
class SignInCubit extends Cubit<SignInState> {
  SignInCubit({required this._signIn}) : super(const SignInState());

  final SignIn _signIn;

  Future<void> submit({required String email, required String password}) async {
    if (state.isSubmitting) return;
    emit(const SignInState(status: SignInStatus.submitting));
    final result = await _signIn(email: email, password: password);
    emit(
      result.match(
        (failure) =>
            SignInState(status: SignInStatus.failure, failure: failure),
        (_) => const SignInState(status: SignInStatus.succeeded),
      ),
    );
  }
}
