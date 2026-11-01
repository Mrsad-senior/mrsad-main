import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/auth/data/datasources/auth_api_data_source.dart';

import '../../../helpers/fake_http_adapter.dart';

const _username = 'noura@bank.example';

Map<String, dynamic> _loginResponse() {
  return {
    'access_token': 'gateway-jwt',
    'token_type': 'bearer',
    'expires_in': 43200,
    'user': {
      'username': _username,
      'role': 'approver',
      'display_name': 'Noura',
      'lang': 'ar',
    },
  };
}

void main() {
  late FakeHttpAdapter adapter;
  late AuthApiDataSource source;

  setUp(() {
    adapter = FakeHttpAdapter();
    source = AuthApiDataSource(fakeDio(adapter));
  });

  tearDown(() => source.dispose());

  test('starts signed out with no token', () async {
    expect(source.currentReviewer, isNull);
    expect(await source.accessToken(), isNull);
  });

  test('signs in with POST /api/auth/login and keeps the token', () async {
    adapter.on('POST', '/api/auth/login', body: _loginResponse());

    final reviewer = await source.signIn(
      email: ' $_username ',
      password: 'a-strong-passphrase',
    );

    expect(reviewer.email, _username);
    expect(source.currentReviewer?.id, _username);
    expect(await source.accessToken(), 'gateway-jwt');
    expect(adapter.requests.single.data, {
      'username': _username,
      'password': 'a-strong-passphrase',
    });
  });

  test('a 401 means wrong credentials and stays signed out', () async {
    adapter.on(
      'POST',
      '/api/auth/login',
      status: 401,
      body: {'detail': 'Invalid username or password'},
    );

    await expectLater(
      source.signIn(email: _username, password: 'wrong-password'),
      throwsA(isA<InvalidCredentialsException>()),
    );
    expect(source.currentReviewer, isNull);
    expect(await source.accessToken(), isNull);
  });

  test('reports sign-in and sign-out to watchers', () async {
    adapter.on('POST', '/api/auth/login', body: _loginResponse());
    final emails = source.watchReviewer().map((r) => r?.email);
    final expectation = expectLater(
      emails,
      emitsInOrder([null, _username, null]),
    );
    await Future<void>.delayed(Duration.zero);

    await source.signIn(email: _username, password: 'a-strong-passphrase');
    await source.signOut();

    await expectation;
    expect(await source.accessToken(), isNull);
  });
}
