import 'package:equatable/equatable.dart';

/// The signed-in gateway account, as `GET /api/auth/me` reports it.
class Account extends Equatable {
  const Account({
    required this.username,
    required this.role,
    this.displayName = '',
    this.language = 'en',
  });

  final String username;

  /// `admin`, `approver` or `auditor`.
  final String role;

  /// Empty when the admin set none.
  final String displayName;

  /// The account's preferred language code, e.g. `ar`.
  final String language;

  /// The display name, or the username without one.
  String get name => displayName.trim().isEmpty ? username : displayName;

  @override
  List<Object?> get props => [username, role, displayName, language];
}
