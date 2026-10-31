import 'package:mirsad/features/auth/domain/entities/reviewer.dart';

/// A reviewer as the auth data sources report them.
class ReviewerModel {
  const ReviewerModel({required this.id, required this.email});

  final String id;
  final String email;

  Reviewer toEntity() => Reviewer(id: id, email: email);
}
