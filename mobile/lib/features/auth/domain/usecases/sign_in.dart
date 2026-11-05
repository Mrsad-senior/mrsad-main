import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';

class SignIn {
  const SignIn(this._repository);

  final AuthRepository _repository;

  /// Surrounding spaces in [username] are dropped; [password] is sent as
  /// typed.
  Future<Either<Failure, Reviewer>> call({
    required String username,
    required String password,
  }) {
    return _repository.signIn(username: username.trim(), password: password);
  }
}
