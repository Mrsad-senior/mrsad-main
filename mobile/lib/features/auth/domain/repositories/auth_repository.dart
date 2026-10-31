import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';

abstract interface class AuthRepository {
  /// The signed-in reviewer, or null when signed out.
  Reviewer? get currentReviewer;

  /// Emits the signed-in reviewer (or null) whenever it changes.
  Stream<Reviewer?> watchReviewer();

  Future<Either<Failure, Reviewer>> signIn({
    required String email,
    required String password,
  });

  Future<Either<Failure, Unit>> signOut();
}
