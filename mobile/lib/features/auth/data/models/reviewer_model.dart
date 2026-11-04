import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

/// A reviewer as the auth data sources report them.
class ReviewerModel {
  const ReviewerModel({
    required this.id,
    required this.username,
    required this.role,
  });

  final String id;
  final String username;
  final ReviewerRole role;

  Reviewer toEntity() => Reviewer(id: id, username: username, role: role);
}
