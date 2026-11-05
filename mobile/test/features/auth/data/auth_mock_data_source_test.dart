import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/auth/data/datasources/auth_mock_data_source.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

void main() {
  late AuthMockDataSource source;

  setUp(() => source = AuthMockDataSource(latency: Duration.zero));

  tearDown(() => source.dispose());

  test('starts signed out with no token', () async {
    expect(source.currentReviewer, isNull);
    expect(await source.accessToken(), isNull);
  });

  test('signs in with any username and a long enough password', () async {
    final reviewer = await source.signIn(
      username: 'reviewer@bank.example',
      password: 'secret123',
    );

    expect(reviewer.username, 'reviewer@bank.example');
    expect(source.currentReviewer, isNotNull);
    expect(await source.accessToken(), AuthMockDataSource.token);
  });

  test('the username picks the role, admin by default', () async {
    expect(AuthMockDataSource.roleFor('approver'), ReviewerRole.approver);
    expect(
      AuthMockDataSource.roleFor('Auditor@bank.example'),
      ReviewerRole.auditor,
    );
    expect(
      AuthMockDataSource.roleFor('reviewer@bank.example'),
      ReviewerRole.admin,
    );

    final reviewer = await source.signIn(
      username: 'approver',
      password: 'secret123',
    );
    expect(reviewer.role, ReviewerRole.approver);
  });

  test('refuses a short password', () async {
    await expectLater(
      source.signIn(username: 'reviewer@bank.example', password: '123'),
      throwsA(isA<InvalidCredentialsException>()),
    );
  });

  test('reports sign-in and sign-out to watchers', () async {
    final usernames = source.watchReviewer().map((r) => r?.username);
    final expectation = expectLater(
      usernames,
      emitsInOrder([null, 'reviewer@bank.example', null]),
    );
    await Future<void>.delayed(Duration.zero);

    await source.signIn(
      username: 'reviewer@bank.example',
      password: 'secret123',
    );
    await source.signOut();

    await expectation;
  });
}
