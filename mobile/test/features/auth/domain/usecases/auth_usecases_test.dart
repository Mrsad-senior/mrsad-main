import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/usecases/get_current_reviewer.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_in.dart';
import 'package:mirsad/features/auth/domain/usecases/sign_out.dart';
import 'package:mirsad/features/auth/domain/usecases/watch_reviewer.dart';
import 'package:mocktail/mocktail.dart';

import '../../auth_mocks.dart';

void main() {
  late MockAuthRepository repository;

  setUp(() => repository = MockAuthRepository());

  group('SignIn', () {
    test('trims the email and keeps the password as typed', () async {
      when(
        () => repository.signIn(
          email: any(named: 'email'),
          password: any(named: 'password'),
        ),
      ).thenAnswer((_) async => const Right(reviewer));

      final result = await SignIn(repository)(
        email: '  reviewer@bank.example ',
        password: ' secret ',
      );

      expect(result, const Right<Failure, Reviewer>(reviewer));
      verify(
        () => repository.signIn(
          email: 'reviewer@bank.example',
          password: ' secret ',
        ),
      ).called(1);
    });

    test('returns InvalidCredentialsFailure from the repository', () async {
      when(
        () => repository.signIn(
          email: any(named: 'email'),
          password: any(named: 'password'),
        ),
      ).thenAnswer((_) async => const Left(InvalidCredentialsFailure()));

      expect(
        await SignIn(repository)(email: 'a@b.example', password: 'wrong'),
        const Left<Failure, Reviewer>(InvalidCredentialsFailure()),
      );
    });
  });

  test('SignOut asks the repository to sign out', () async {
    when(() => repository.signOut()).thenAnswer((_) async => const Right(unit));

    expect(await SignOut(repository)(), const Right<Failure, Unit>(unit));
    verify(() => repository.signOut()).called(1);
  });

  test('WatchReviewer drops repeated values', () async {
    when(() => repository.watchReviewer()).thenAnswer(
      (_) => Stream.fromIterable([null, null, reviewer, reviewer, null]),
    );

    expect(await WatchReviewer(repository)().toList(), [null, reviewer, null]);
  });

  test('GetCurrentReviewer returns who is signed in now', () {
    when(() => repository.currentReviewer).thenReturn(reviewer);
    expect(GetCurrentReviewer(repository)(), reviewer);
  });
}
