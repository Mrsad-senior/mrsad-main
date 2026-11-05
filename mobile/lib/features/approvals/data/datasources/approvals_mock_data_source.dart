import 'dart:async';

import 'package:mirsad/core/errors/exceptions.dart';
import 'package:mirsad/core/utils/clock.dart';
import 'package:mirsad/features/approvals/data/datasources/approvals_data_source.dart';
import 'package:mirsad/features/approvals/data/datasources/mock/demo_approvals.dart';
import 'package:mirsad/features/approvals/data/models/approval_model.dart';
import 'package:mirsad/features/approvals/data/models/decision_request_model.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';

/// In-memory approvals that behave like the gateway: decisions change the
/// status, and held actions expire after [approvalWindow].
///
/// Pull to refresh on an empty list brings the demo approvals back.
class ApprovalsMockDataSource
    implements ApprovalsReadDataSource, ApprovalDecisionDataSource {
  ApprovalsMockDataSource({
    required this._clock,
    this.latency = const Duration(milliseconds: 400),
  }) {
    _seed();
  }

  /// Simulated network delay.
  final Duration latency;

  final Clock _clock;
  final Map<String, ApprovalModel> _store = {};
  final StreamController<void> _changes = StreamController.broadcast();

  @override
  Stream<List<ApprovalModel>> watchPending() async* {
    await _delay();
    yield _pending();
    yield* _changes.stream.map((_) => _pending());
  }

  @override
  Future<void> refreshPending() async {
    await _delay();
    if (_pending().isEmpty) _seed();
    _changes.add(null);
  }

  @override
  Future<ApprovalModel> getApproval(String id) async {
    await _delay();
    return _current(id) ?? (throw NotFoundException('No approval $id'));
  }

  @override
  Future<ApprovalModel> submitDecision(
    String id,
    DecisionRequestModel request,
  ) async {
    await _delay();
    final approval =
        _current(id) ?? (throw NotFoundException('No approval $id'));
    if (approval.status != ApprovalStatus.held) {
      throw ConflictException('Approval $id is ${approval.status.name}');
    }
    final decided = approval.copyWith(
      status: request.decision == ReviewDecision.approve
          ? ApprovalStatus.approved
          : ApprovalStatus.rejected,
    );
    _store[id] = decided;
    _changes.add(null);
    return decided;
  }

  Future<void> dispose() => _changes.close();

  void _seed() {
    for (final approval in demoApprovals(_clock.now())) {
      _store[approval.id] = approval;
    }
  }

  Future<void> _delay() => Future<void>.delayed(latency);

  List<ApprovalModel> _pending() {
    return _store.keys
        .toList()
        .map(_current)
        .whereType<ApprovalModel>()
        .where((approval) => approval.status == ApprovalStatus.held)
        .toList();
  }

  /// The stored approval, marked expired if its deadline has passed.
  ApprovalModel? _current(String id) {
    final approval = _store[id];
    if (approval == null) return null;
    final overdue = !_clock.now().isBefore(approval.expiresAt);
    if (approval.status == ApprovalStatus.held && overdue) {
      return _store[id] = approval.copyWith(status: ApprovalStatus.expired);
    }
    return approval;
  }
}
