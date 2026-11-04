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

  ReviewerModel toReviewer() => ReviewerModel(id: username, username: username);
}

Object? _readUsername(Map<dynamic, dynamic> json, String _) {
  final user = json['user'];
  return user is Map ? user['username'] : null;
}
