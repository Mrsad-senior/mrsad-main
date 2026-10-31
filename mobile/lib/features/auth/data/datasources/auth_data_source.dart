import 'package:mirsad/features/auth/data/models/reviewer_model.dart';

/// Reviewer sign-in. Implemented by the mock and Supabase sources; the
/// gateway does not sign anyone in. Methods throw `AppException`s.
abstract interface class AuthDataSource {
  ReviewerModel? get currentReviewer;

  /// Emits the current reviewer (or null) first, then every change.
  Stream<ReviewerModel?> watchReviewer();

  Future<ReviewerModel> signIn({
    required String email,
    required String password,
  });

  Future<void> signOut();

  /// The token the gateway API expects as `Authorization: Bearer`. Null when
  /// signed out.
  Future<String?> accessToken();
}
