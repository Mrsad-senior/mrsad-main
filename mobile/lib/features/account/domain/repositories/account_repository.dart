import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';

abstract interface class AccountRepository {
  /// The signed-in account, read fresh from the gateway.
  Future<Either<Failure, Account>> getAccount();
}
