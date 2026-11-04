import 'package:equatable/equatable.dart';

/// The person signed in to review held actions.
class Reviewer extends Equatable {
  const Reviewer({required this.id, required this.username});

  final String id;

  /// The gateway account name, e.g. `admin` or `noura@bank.example`.
  final String username;

  @override
  List<Object?> get props => [id, username];
}
