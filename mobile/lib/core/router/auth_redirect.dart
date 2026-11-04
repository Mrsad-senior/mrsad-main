import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// Where to send someone at [location] given their sign-in [status] and
/// [role], or null to let them stay. A signed-in reviewer who opens a tab
/// their role cannot use is sent to their first tab instead.
String? authRedirect({
  required AuthStatus status,
  required String location,
  ReviewerRole? role,
}) {
  final onSignIn = location == AppRoutes.signIn;
  switch (status) {
    case AuthStatus.unknown:
      return null;
    case AuthStatus.unauthenticated:
      return onSignIn ? null : AppRoutes.signIn;
    case AuthStatus.authenticated:
      // Every role may open Audit, so it is the fallback without a role.
      final home = role == null ? AppRoutes.audit : homeFor(role);
      if (onSignIn) return home;
      return role == null || canOpen(role, location) ? null : home;
  }
}

/// Whether [role] may open [location]. Mirrors the gateway's role table, so
/// nobody lands on a tab that can only answer 403.
bool canOpen(ReviewerRole role, String location) {
  if (_isUnder(location, AppRoutes.approvals)) return role.canReviewApprovals;
  if (_isUnder(location, AppRoutes.activity)) return role.canReadAudit;
  return true;
}

/// The first tab [role] sees after signing in.
String homeFor(ReviewerRole role) =>
    role.canReviewApprovals ? AppRoutes.approvals : AppRoutes.audit;

bool _isUnder(String location, String path) =>
    location == path || location.startsWith('$path/');
