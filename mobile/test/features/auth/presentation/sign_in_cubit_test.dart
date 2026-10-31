import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/presentation/cubit/sign_in_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../auth_mocks.dart';

void main() {
  late MockSignIn signIn;

  setUp(() => signIn = MockSignIn());

  SignInCubit build() => SignInCubit(signIn: signIn);

  void whenSignIn(Either<Failure, Reviewer> result) {
    when(
      () => signIn(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    ).thenAnswer((_) async => result);
  }

  blocTest<SignInCubit, SignInState>(
    'submits and succeeds',
    setUp: () => whenSignIn(const Right(reviewer)),
    build: build,
    act: (cubit) =>
        cubit.submit(email: 'reviewer@bank.example', password: 'secret123'),
    expect: () => const [
      SignInState(status: SignInStatus.submitting),
      SignInState(status: SignInStatus.succeeded),
    ],
    verify: (_) => verify(
      () => signIn(email: 'reviewer@bank.example', password: 'secret123'),
    ).called(1),
  );

  blocTest<SignInCubit, SignInState>(
    'shows why sign-in failed',
    setUp: () => whenSignIn(const Left(InvalidCredentialsFailure())),
    build: build,
    act: (cubit) => cubit.submit(email: 'a@b.example', password: 'wrong-pass'),
    expect: () => const [
      SignInState(status: SignInStatus.submitting),
      SignInState(
        status: SignInStatus.failure,
        failure: InvalidCredentialsFailure(),
      ),
    ],
  );

  blocTest<SignInCubit, SignInState>(
    'ignores a second submit while the first is running',
    build: build,
    seed: () => const SignInState(status: SignInStatus.submitting),
    act: (cubit) => cubit.submit(email: 'a@b.example', password: 'secret123'),
    expect: () => const <SignInState>[],
  );
}
