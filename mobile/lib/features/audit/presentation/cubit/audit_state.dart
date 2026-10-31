part of 'audit_cubit.dart';

enum AuditStatus { loading, ready, failure }

class AuditState extends Equatable {
  const AuditState({
    this.status = AuditStatus.loading,
    this.result,
    this.failure,
    this.verifying = false,
  });

  final AuditStatus status;

  /// The last verification result.
  final AuditChainStatus? result;

  /// Why the last verification failed. With [AuditStatus.ready] the previous
  /// result stays on screen and this is reported in a snackbar.
  final Failure? failure;

  /// A new verification is running while [result] is shown.
  final bool verifying;

  @override
  List<Object?> get props => [status, result, failure, verifying];
}
