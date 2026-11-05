import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/account/data/datasources/account_data_source.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';
import 'package:mirsad/features/account/domain/repositories/account_repository.dart';

class AccountRepositoryImpl implements AccountRepository {
  const AccountRepositoryImpl(this._source);

  final AccountDataSource _source;

  @override
  Future<Either<Failure, Account>> getAccount() {
    return guard(() async => (await _source.me()).toEntity());
  }
}
