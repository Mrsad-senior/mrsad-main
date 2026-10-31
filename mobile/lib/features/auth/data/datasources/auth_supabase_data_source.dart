import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/network/supabase_error_mapping.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';
import 'package:mirsad/features/auth/data/models/reviewer_model.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Email and password sign-in with Supabase Auth. Supabase keeps the session
/// on the device and refreshes its token.
class AuthSupabaseDataSource implements AuthDataSource {
  AuthSupabaseDataSource(this._client);

  final SupabaseClient _client;

  GoTrueClient get _auth => _client.auth;

  @override
  ReviewerModel? get currentReviewer => _toModel(_auth.currentUser);

  @override
  Stream<ReviewerModel?> watchReviewer() async* {
    yield currentReviewer;
    yield* _auth.onAuthStateChange.map(
      (change) => _toModel(change.session?.user),
    );
  }

  @override
  Future<ReviewerModel> signIn({
    required String email,
    required String password,
  }) {
    return callSupabase(() async {
      final response = await _auth.signInWithPassword(
        email: email,
        password: password,
      );
      return _toModel(response.user) ??
          (throw const InvalidCredentialsException('No user returned'));
    });
  }

  @override
  Future<void> signOut() => callSupabase(_auth.signOut);

  @override
  Future<String?> accessToken() async => _auth.currentSession?.accessToken;

  ReviewerModel? _toModel(User? user) {
    if (user == null) return null;
    return ReviewerModel(id: user.id, email: user.email ?? '');
  }
}
