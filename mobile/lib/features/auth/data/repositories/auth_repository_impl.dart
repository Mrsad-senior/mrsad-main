import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/errors/guard.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';

class AuthRepositoryImpl implements AuthRepository {
  const AuthRepositoryImpl(this._source);

  final AuthDataSource _source;

  @override
  Reviewer? get currentReviewer => _source.currentReviewer?.toEntity();

  @override
  Stream<Reviewer?> watchReviewer() {
    // An error here (e.g. a failed token refresh) keeps the current state.
    // If the session is really gone, Supabase emits a sign-out by itself.
    return _source
        .watchReviewer()
        .map((model) => model?.toEntity())
        .handleError((Object _) {});
  }

  @override
  Future<Either<Failure, Reviewer>> signIn({
    required String email,
    required String password,
  }) {
    return guard(
      () async =>
          (await _source.signIn(email: email, password: password)).toEntity(),
    );
  }

  @override
  Future<Either<Failure, Unit>> signOut() {
    return guard(() async {
      await _source.signOut();
      return unit;
    });
  }
}
