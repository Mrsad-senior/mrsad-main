import 'dart:async';

import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/features/auth/data/datasources/auth_data_source.dart';
import 'package:mirsad/features/auth/data/models/reviewer_model.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

/// Accepts any username with a password of [minPasswordLength] or more
/// characters. Starts signed out on every launch.
///
/// The username picks the role, to try each role's tabs: `approver` and
/// `auditor` (or `approver@…`, `auditor@…`) get those roles, anyone else is
/// an admin.
class AuthMockDataSource implements AuthDataSource {
  AuthMockDataSource({this.latency = const Duration(milliseconds: 600)});

  static const minPasswordLength = 6;
  static const token = 'mock-token';

  /// Simulated network delay.
  final Duration latency;

  ReviewerModel? _reviewer;
  final StreamController<ReviewerModel?> _changes =
      StreamController.broadcast();

  @override
  ReviewerModel? get currentReviewer => _reviewer;

  @override
  Stream<ReviewerModel?> watchReviewer() async* {
    yield _reviewer;
    yield* _changes.stream;
  }

  @override
  Future<ReviewerModel> signIn({
    required String username,
    required String password,
  }) async {
    await Future<void>.delayed(latency);
    if (password.length < minPasswordLength) {
      throw const InvalidCredentialsException('Mock password too short');
    }
    final reviewer = ReviewerModel(
      id: 'mock-reviewer',
      username: username,
      role: roleFor(username),
    );
    _set(reviewer);
    return reviewer;
  }

  @override
  Future<void> signOut() async => _set(null);

  @override
  Future<String?> accessToken() async => _reviewer == null ? null : token;

  Future<void> dispose() => _changes.close();

  static ReviewerRole roleFor(String username) {
    final name = username.trim().toLowerCase().split('@').first;
    return switch (name) {
      'approver' => ReviewerRole.approver,
      'auditor' => ReviewerRole.auditor,
      _ => ReviewerRole.admin,
    };
  }

  void _set(ReviewerModel? reviewer) {
    _reviewer = reviewer;
    _changes.add(reviewer);
  }
}
