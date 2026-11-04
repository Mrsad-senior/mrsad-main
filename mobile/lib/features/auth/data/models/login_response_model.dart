import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/auth/data/models/reviewer_model.dart';
import 'package:mirsad/features/auth/data/models/user_model.dart';

part 'login_response_model.g.dart';

/// Response of `POST /api/auth/login`. Only the fields the app uses are read.
@JsonSerializable(createToJson: false)
class LoginResponseModel {
  const LoginResponseModel({required this.accessToken, required this.user});

  factory LoginResponseModel.fromJson(Map<String, dynamic> json) =>
      _$LoginResponseModelFromJson(json);

  /// The gateway's own JWT, sent back as `Authorization: Bearer`.
  final String accessToken;

  final UserModel user;

  ReviewerModel toReviewer() => ReviewerModel(
    id: user.username,
    username: user.username,
    role: user.role,
  );
}
