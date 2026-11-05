/// Where a held action is in its review.
enum ApprovalStatus {
  /// Waiting for a reviewer.
  held,
  approved,
  rejected,

  /// Nobody decided in time, so the gateway auto-rejected it.
  expired,
}
