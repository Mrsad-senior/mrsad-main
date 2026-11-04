/// A gateway account's role. What each role may call is the "Roles" table in
/// docs/api.md; the gateway enforces it, the app only hides what would fail.
enum ReviewerRole {
  admin,
  approver,
  auditor;

  /// Pending approvals and decisions (`/api/approvals`).
  bool get canReviewApprovals => this == admin || this == approver;

  /// Audit events (`/api/audit/*`), which the activity feed reads.
  bool get canReadAudit => this == admin || this == auditor;

  /// The detector playground (`POST /api/detector/scan`) is open to every
  /// role.
  bool get canUseDetector => true;
}
