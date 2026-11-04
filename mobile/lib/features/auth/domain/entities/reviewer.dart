import 'package:equatable/equatable.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

/// The person signed in to review held actions.
class Reviewer extends Equatable {
  const Reviewer({
    required this.id,
    required this.username,
    required this.role,
  });

  final String id;

  /// The gateway account name, e.g. `admin` or `noura@bank.example`.
  final String username;

  /// From the login response; decides which tabs the app shows.
  final ReviewerRole role;

  @override
  List<Object?> get props => [id, username, role];
}
