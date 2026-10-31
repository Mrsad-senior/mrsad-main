import 'dart:async';

import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/usecases/refresh_pending_approvals.dart';
import 'package:mirsad/features/approvals/domain/usecases/watch_pending_approvals.dart';

part 'pending_approvals_state.dart';

class PendingApprovalsCubit extends Cubit<PendingApprovalsState> {
  PendingApprovalsCubit({
    required this._watchPending,
    required this._refreshPending,
  }) : super(const PendingApprovalsState());

  final WatchPendingApprovals _watchPending;
  final RefreshPendingApprovals _refreshPending;
  StreamSubscription<Either<Failure, List<Approval>>>? _subscription;

  /// Starts following the pending list. Calling it again does nothing.
  void start() {
    _subscription ??= _watchPending().listen(
      (result) => result.match(_onFailure, _onApprovals),
    );
  }

  /// Pull-to-refresh. The new list arrives through the subscription.
  Future<void> refresh() async {
    final result = await _refreshPending();
    result.match(_onFailure, (_) {});
  }

  /// Starts over after the first load failed.
  Future<void> retry() async {
    await _subscription?.cancel();
    _subscription = null;
    emit(const PendingApprovalsState());
    start();
  }

  void _onApprovals(List<Approval> approvals) {
    emit(
      PendingApprovalsState(
        status: PendingApprovalsStatus.ready,
        approvals: approvals,
      ),
    );
  }

  void _onFailure(Failure failure) {
    final hadList = state.status == PendingApprovalsStatus.ready;
    emit(
      PendingApprovalsState(
        status: hadList
            ? PendingApprovalsStatus.ready
            : PendingApprovalsStatus.failure,
        approvals: state.approvals,
        failure: failure,
      ),
    );
  }

  @override
  Future<void> close() async {
    await _subscription?.cancel();
    return super.close();
  }
}
