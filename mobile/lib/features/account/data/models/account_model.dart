import 'package:json_annotation/json_annotation.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';

part 'account_model.g.dart';

/// `GET /api/auth/me` (`UserOut` in src/mirsad/api/schemas.py).
@JsonSerializable(createToJson: false)
class AccountModel {
  const AccountModel({
    required this.username,
    required this.role,
    this.displayName = '',
    this.lang = 'en',
  });

  factory AccountModel.fromJson(Map<String, dynamic> json) =>
      _$AccountModelFromJson(json);

  final String username;
  final String role;

  @JsonKey(defaultValue: '')
  final String displayName;

  @JsonKey(defaultValue: 'en')
  final String lang;

  Account toEntity() => Account(
    username: username,
    role: role,
    displayName: displayName,
    language: lang,
  );
}
