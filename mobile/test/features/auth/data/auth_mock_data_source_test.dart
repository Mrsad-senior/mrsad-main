import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/auth/data/datasources/auth_mock_data_source.dart';

void main() {
  late AuthMockDataSource source;

  setUp(() => source = AuthMockDataSource(latency: Duration.zero));

  tearDown(() => source.dispose());

  test('starts signed out with no token', () async {
    expect(source.currentReviewer, isNull);
    expect(await source.accessToken(), isNull);
  });

  test('signs in with any email and a long enough password', () async {
    final reviewer = await source.signIn(
      email: 'reviewer@bank.example',
      password: 'secret123',
    );

    expect(reviewer.email, 'reviewer@bank.example');
    expect(source.currentReviewer, isNotNull);
    expect(await source.accessToken(), AuthMockDataSource.token);
  });

  test('refuses a short password', () async {
    await expectLater(
      source.signIn(email: 'reviewer@bank.example', password: '123'),
      throwsA(isA<InvalidCredentialsException>()),
    );
  });

  test('reports sign-in and sign-out to watchers', () async {
    final emails = source.watchReviewer().map((r) => r?.email);
    final expectation = expectLater(
      emails,
      emitsInOrder([null, 'reviewer@bank.example', null]),
    );
    await Future<void>.delayed(Duration.zero);

    await source.signIn(email: 'reviewer@bank.example', password: 'secret123');
    await source.signOut();

    await expectation;
  });
}
