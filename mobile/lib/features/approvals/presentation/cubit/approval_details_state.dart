part of 'approval_details_cubit.dart';

enum ApprovalDetailsStatus { loading, ready, failure }

/// Progress of the reviewer's approve / reject request.
enum DecisionSubmission { idle, submitting, succeeded, failed }

class ApprovalDetailsState extends Equatable {
  const ApprovalDetailsState({
    this.status = ApprovalDetailsStatus.loading,
    this.approval,
    this.loadFailure,
    this.submission = DecisionSubmission.idle,
    this.decision,
    this.submitFailure,
  });

  final ApprovalDetailsStatus status;
  final Approval? approval;

  /// Why the approval could not be loaded.
  final Failure? loadFailure;

  final DecisionSubmission submission;

  /// The decision being, or last, submitted.
  final ReviewDecision? decision;

  /// Why the last decision was not accepted.
  final Failure? submitFailure;

  bool get isSubmitting => submission == DecisionSubmission.submitting;

  @override
  List<Object?> get props => [
    status,
    approval,
    loadFailure,
    submission,
    decision,
    submitFailure,
  ];
}
