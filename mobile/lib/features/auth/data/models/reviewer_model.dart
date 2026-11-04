import 'package:mirsad/features/auth/domain/entities/reviewer.dart';

/// A reviewer as the auth data sources report them.
class ReviewerModel {
  const ReviewerModel({required this.id, required this.username});

  final String id;
  final String username;

  Reviewer toEntity() => Reviewer(id: id, username: username);
}
