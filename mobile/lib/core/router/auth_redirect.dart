import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// Where to send someone at [location] given their sign-in [status] and
/// [role], or null to let them stay. Signed-in reviewers start on Home,
/// which every role may open, and are sent back there from a screen their
/// role cannot use.
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
      if (onSignIn) return AppRoutes.home;
      return role == null || canOpen(role, location) ? null : AppRoutes.home;
  }
}

/// Whether [role] may open [location]. Mirrors the gateway's role table, so
/// nobody lands on a tab that can only answer 403.
bool canOpen(ReviewerRole role, String location) {
  if (_isUnder(location, AppRoutes.approvals)) return role.canReviewApprovals;
  if (_isUnder(location, AppRoutes.activity)) return role.canReadAudit;
  if (_isUnder(location, AppRoutes.detector)) return role.canUseDetector;
  return true;
}

bool _isUnder(String location, String path) =>
    location == path || location.startsWith('$path/');
