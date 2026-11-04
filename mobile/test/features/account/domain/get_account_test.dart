import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';
import 'package:mirsad/features/account/domain/usecases/get_account.dart';
import 'package:mocktail/mocktail.dart';

import '../account_mocks.dart';

void main() {
  test('GetAccount asks the repository', () async {
    final repository = MockAccountRepository();
    when(repository.getAccount).thenAnswer((_) async => const Right(noura));

    expect(
      await GetAccount(repository)(),
      const Right<Failure, Account>(noura),
    );
  });

  test('name falls back to the username', () {
    expect(noura.name, 'Noura');
    expect(
      const Account(username: 'admin', role: 'admin', displayName: ' ').name,
      'admin',
    );
  });
}
