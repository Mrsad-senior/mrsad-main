part of 'pending_approvals_cubit.dart';

enum PendingApprovalsStatus { loading, ready, failure }

class PendingApprovalsState extends Equatable {
  const PendingApprovalsState({
    this.status = PendingApprovalsStatus.loading,
    this.approvals = const [],
    this.failure,
  });

  final PendingApprovalsStatus status;

  /// Most urgent first.
  final List<Approval> approvals;

  /// The latest failure. With [PendingApprovalsStatus.ready] the list stays
  /// on screen and the failure is reported in a snackbar.
  final Failure? failure;

  @override
  List<Object?> get props => [status, approvals, failure];
}
