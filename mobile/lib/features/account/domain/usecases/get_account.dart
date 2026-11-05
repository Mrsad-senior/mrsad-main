import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';
import 'package:mirsad/features/account/domain/repositories/account_repository.dart';

class GetAccount {
  const GetAccount(this._repository);

  final AccountRepository _repository;

  Future<Either<Failure, Account>> call() => _repository.getAccount();
}
