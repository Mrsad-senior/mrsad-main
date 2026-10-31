import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/repositories/auth_repository.dart';

/// The signed-in reviewer right now, or null.
class GetCurrentReviewer {
  const GetCurrentReviewer(this._repository);

  final AuthRepository _repository;

  Reviewer? call() => _repository.currentReviewer;
}
