import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/account/data/datasources/account_api_data_source.dart';
import 'package:mirsad/features/account/data/datasources/account_mock_data_source.dart';
import 'package:mirsad/features/account/data/models/account_model.dart';
import 'package:mirsad/features/account/data/repositories/account_repository_impl.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';
import 'package:mocktail/mocktail.dart';

import '../../../helpers/fake_http_adapter.dart';
import '../account_mocks.dart';

void main() {
  group('AccountApiDataSource', () {
    late FakeHttpAdapter adapter;

    setUp(() => adapter = FakeHttpAdapter());

    test('reads GET /api/auth/me', () async {
      adapter.on(
        'GET',
        '/api/auth/me',
        body: {
          'username': 'noura@bank.example',
          'role': 'approver',
          'display_name': 'Noura',
          'lang': 'ar',
        },
      );

      final model = await AccountApiDataSource(fakeDio(adapter)).me();

      expect(model.toEntity(), noura);
    });

    test('a 401 is an UnauthorizedException', () async {
      adapter.on('GET', '/api/auth/me', status: 401);
      await expectLater(
        AccountApiDataSource(fakeDio(adapter)).me(),
        throwsA(isA<UnauthorizedException>()),
      );
    });
  });

  test('the model defaults a missing display name and language', () {
    final account = AccountModel.fromJson(const {
      'username': 'admin',
      'role': 'admin',
    }).toEntity();
    expect(account.displayName, isEmpty);
    expect(account.language, 'en');
    expect(account.name, 'admin');
  });

  group('AccountMockDataSource', () {
    test('reports the mock session', () async {
      final source = AccountMockDataSource(
        () => const AccountModel(username: 'approver', role: 'approver'),
      );
      expect((await source.me()).role, 'approver');
    });

    test('is unauthorised while signed out', () async {
      await expectLater(
        AccountMockDataSource(() => null).me(),
        throwsA(isA<UnauthorizedException>()),
      );
    });
  });

  group('AccountRepositoryImpl', () {
    late MockAccountDataSource source;

    setUp(() => source = MockAccountDataSource());

    test('maps the model to an entity', () async {
      when(() => source.me()).thenAnswer(
        (_) async => const AccountModel(
          username: 'noura@bank.example',
          role: 'approver',
          displayName: 'Noura',
          lang: 'ar',
        ),
      );
      expect(
        await AccountRepositoryImpl(source).getAccount(),
        const Right<Failure, Account>(noura),
      );
    });

    test('maps exceptions to failures', () async {
      when(() => source.me()).thenThrow(const NetworkException());
      expect(
        await AccountRepositoryImpl(source).getAccount(),
        const Left<Failure, Account>(NetworkFailure()),
      );
    });
  });
}
