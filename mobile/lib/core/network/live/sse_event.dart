import 'package:equatable/equatable.dart';

/// One Server-Sent Event from the gateway's `GET /api/stream`.
class SseEvent extends Equatable {
  const SseEvent(this.event, this.data);

  /// The gateway's event names (docs/api.md, "Live stream").
  static const ready = 'ready';
  static const approvalRequested = 'approval.requested';
  static const approvalDecided = 'approval.decided';
  static const auditEvent = 'audit.event';

  /// The `event:` field; `message` when the server sent none.
  final String event;

  /// The `data:` lines joined with newlines. JSON for every gateway event.
  final String data;

  bool get isApproval => event == approvalRequested || event == approvalDecided;

  @override
  List<Object?> get props => [event, data];
}
