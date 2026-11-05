import 'package:json_annotation/json_annotation.dart';

part 'login_request_model.g.dart';

/// Body of `POST /api/auth/login`. The gateway rejects unknown fields.
@JsonSerializable(createFactory: false)
class LoginRequestModel {
  const LoginRequestModel({required this.username, required this.password});

  final String username;
  final String password;

  Map<String, dynamic> toJson() => _$LoginRequestModelToJson(this);
}
