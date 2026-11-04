import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';

part 'user_model.g.dart';

/// The `user` object of `POST /api/auth/login` (`UserOut` in
/// src/mirsad/api/schemas.py). Only the fields the app uses are read.
@JsonSerializable(createToJson: false)
class UserModel {
  const UserModel({required this.username, required this.role});

  factory UserModel.fromJson(Map<String, dynamic> json) =>
      _$UserModelFromJson(json);

  final String username;

  @JsonKey(fromJson: reviewerRoleFromJson)
  final ReviewerRole role;
}

/// The gateway's role names are the enum's names. Anything else is a format
/// error, so an unknown role never gets more than it should.
ReviewerRole reviewerRoleFromJson(String value) {
  return ReviewerRole.values.asNameMap()[value] ??
      (throw FormatException('Unknown role "$value"'));
}
