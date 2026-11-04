import 'package:equatable/equatable.dart';

/// How the gateway decided on one tool's calls.
class ToolActivity extends Equatable {
  const ToolActivity({
    required this.tool,
    required this.allowed,
    required this.denied,
    required this.held,
  });

  /// The tool name as agents call it, e.g. `transfer_funds`.
  final String tool;

  final int allowed;
  final int denied;
  final int held;

  int get total => allowed + denied + held;

  @override
  List<Object?> get props => [tool, allowed, denied, held];
}
