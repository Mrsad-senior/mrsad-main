import 'package:equatable/equatable.dart';

/// The person signed in to review held actions.
class Reviewer extends Equatable {
  const Reviewer({required this.id, required this.email});

  final String id;
  final String email;

  @override
  List<Object?> get props => [id, email];
}
