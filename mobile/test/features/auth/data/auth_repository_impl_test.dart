import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/data/models/reviewer_model.dart';
import 'package:mirsad/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mocktail/mocktail.dart';

import '../auth_mocks.dart';

const _model = ReviewerModel(id: 'rev_1', email: 'reviewer@bank.example');

void main() {
  late MockAuthDataSource source;
  late AuthRepositoryImpl repository;

  setUp(() {
    source = MockAuthDataSource();
    repository = AuthRepositoryImpl(source);
  });

  test('currentReviewer maps the model to an entity', () {
    when(() => source.currentReviewer).thenReturn(_model);
    expect(repository.currentReviewer, reviewer);
  });

  test('watchReviewer maps models and ignores stream errors', () async {
    when(() => source.watchReviewer()).thenAnswer(
      (_) => Stream.fromFutures([
        Future<ReviewerModel?>.value(_model),
        Future<ReviewerModel?>.error(const NetworkException()),
        Future<ReviewerModel?>.value(),
      ]),
    );

    expect(await repository.watchReviewer().toList(), [reviewer, null]);
  });

  test('signIn returns the reviewer', () async {
    when(
      () => source.signIn(email: 'reviewer@bank.example', password: 'secret'),
    ).thenAnswer((_) async => _model);

    expect(
      await repository.signIn(
        email: 'reviewer@bank.example',
        password: 'secret',
      ),
      const Right<Failure, Reviewer>(reviewer),
    );
  });

  test('signIn maps wrong credentials to a failure', () async {
    when(
      () => source.signIn(
        email: any(named: 'email'),
        password: any(named: 'password'),
      ),
    ).thenThrow(const InvalidCredentialsException());

    expect(
      await repository.signIn(email: 'a@b.example', password: 'nope'),
      const Left<Failure, Reviewer>(InvalidCredentialsFailure()),
    );
  });

  test('signOut maps errors to a failure', () async {
    when(() => source.signOut()).thenThrow(const NetworkException());
    expect(
      await repository.signOut(),
      const Left<Failure, Unit>(NetworkFailure()),
    );
  });
}
