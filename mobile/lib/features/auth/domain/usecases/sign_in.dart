import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';

class SignIn {
  const SignIn(this._repository);

  final AuthRepository _repository;

  /// Surrounding spaces in [email] are dropped; [password] is sent as typed.
  Future<Either<Failure, Reviewer>> call({
    required String email,
    required String password,
  }) {
    return _repository.signIn(email: email.trim(), password: password);
  }
}
