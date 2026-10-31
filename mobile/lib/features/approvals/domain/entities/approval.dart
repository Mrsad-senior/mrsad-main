import 'package:equatable/equatable.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_reason.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

/// An agent action that Mirsad held for a human decision.
class Approval extends Equatable {
  const Approval({
    required this.id,
    required this.agentId,
    required this.sector,
    required this.tool,
    required this.arguments,
    required this.status,
    required this.riskScore,
    required this.tainted,
    required this.userTask,
    required this.reasons,
    required this.createdAt,
    required this.expiresAt,
  });

  /// Argument keys that hold the recipient of money or a message, in the
  /// order they are looked up.
  static const recipientKeys = ['to_iban', 'to', 'recipient'];

  final String id;
  final String agentId;
  final Sector sector;

  /// The tool name exactly as the agent called it, e.g. `transfer_funds`.
  final String tool;

  /// The tool call's arguments, unchanged.
  final Map<String, Object?> arguments;

  final ApprovalStatus status;

  /// Between 0 and 1.
  final double riskScore;

  /// Whether any argument came from untrusted content.
  final bool tainted;

  /// What the user originally asked the agent to do.
  final String userTask;

  final List<ApprovalReason> reasons;
  final DateTime createdAt;

  /// When the gateway auto-rejects the action if nobody decides.
  final DateTime expiresAt;

  /// The amount of money the action moves, if it has one.
  num? get amount {
    final value = arguments['amount'];
    return value is num ? value : null;
  }

  String? get currency {
    final value = arguments['currency'];
    return value is String ? value : null;
  }

  /// Who receives the money or message, if the tool has a recipient.
  String? get recipient {
    for (final key in recipientKeys) {
      final value = arguments[key];
      if (value is String && value.isNotEmpty) return value;
    }
    return null;
  }

  /// Whether a reviewer can still approve or reject it at [now].
  bool isOpenAt(DateTime now) =>
      status == ApprovalStatus.held && now.isBefore(expiresAt);

  /// Time left before auto-rejection, never negative.
  Duration timeLeftAt(DateTime now) {
    final left = expiresAt.difference(now);
    return left.isNegative ? Duration.zero : left;
  }

  @override
  List<Object?> get props => [
    id,
    agentId,
    sector,
    tool,
    arguments,
    status,
    riskScore,
    tainted,
    userTask,
    reasons,
    createdAt,
    expiresAt,
  ];
}
