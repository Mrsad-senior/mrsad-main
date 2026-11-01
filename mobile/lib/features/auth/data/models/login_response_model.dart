import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/auth/data/models/reviewer_model.dart';

part 'login_response_model.g.dart';

/// Response of `POST /api/auth/login`. Only the fields the app uses are read.
@JsonSerializable(createToJson: false)
class LoginResponseModel {
  const LoginResponseModel({required this.accessToken, required this.username});

  factory LoginResponseModel.fromJson(Map<String, dynamic> json) =>
      _$LoginResponseModelFromJson(json);

  /// The gateway's own JWT, sent back as `Authorization: Bearer`.
  final String accessToken;

  /// `user.username` in the response.
  @JsonKey(readValue: _readUsername)
  final String username;

  /// Gateway accounts have a username and no email address. The sign-in
  /// form asks for an email, so reviewers use email-style usernames.
  ReviewerModel toReviewer() => ReviewerModel(id: username, email: username);
}

Object? _readUsername(Map<dynamic, dynamic> json, String _) {
  final user = json['user'];
  return user is Map ? user['username'] : null;
}
