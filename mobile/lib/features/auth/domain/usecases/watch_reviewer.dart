import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';

/// Sign-ins and sign-outs, including ones that happen outside the app's
/// control, such as an expired session.
class WatchReviewer {
  const WatchReviewer(this._repository);

  final AuthRepository _repository;

  Stream<Reviewer?> call() => _repository.watchReviewer().distinct();
}
