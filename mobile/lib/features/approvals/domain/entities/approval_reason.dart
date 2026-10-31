import 'package:equatable/equatable.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';

/// Why one Mirsad layer flagged an action.
class ApprovalReason extends Equatable {
  const ApprovalReason({required this.layer, required this.message});

  final ReasonLayer layer;

  /// Human-readable explanation from the gateway, shown as-is.
  final String message;

  @override
  List<Object?> get props => [layer, message];
}
