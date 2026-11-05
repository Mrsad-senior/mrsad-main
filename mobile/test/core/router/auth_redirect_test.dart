import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/core/router/auth_redirect.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer_role.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

String? _signedIn(ReviewerRole role, String location) => authRedirect(
  status: AuthStatus.authenticated,
  location: location,
  role: role,
);

void main() {
  test('sends signed-out reviewers to sign-in', () {
    expect(
      authRedirect(
        status: AuthStatus.unauthenticated,
        location: AppRoutes.approvals,
      ),
      AppRoutes.signIn,
    );
    expect(
      authRedirect(
        status: AuthStatus.unauthenticated,
        location: AppRoutes.signIn,
      ),
      isNull,
    );
  });

  test('sends every signed-in role from sign-in to Home', () {
    for (final role in ReviewerRole.values) {
      expect(_signedIn(role, AppRoutes.signIn), AppRoutes.home);
      expect(_signedIn(role, AppRoutes.home), isNull);
      expect(_signedIn(role, AppRoutes.audit), isNull);
      expect(_signedIn(role, AppRoutes.account), isNull);
      expect(_signedIn(role, AppRoutes.chat), isNull);
    }
  });

  test('lets every role open the detector, as the gateway does', () {
    for (final role in ReviewerRole.values) {
      expect(_signedIn(role, AppRoutes.detector), isNull);
    }
  });

  test('keeps approvers off the activity feed (audit is admin/auditor)', () {
    expect(
      _signedIn(ReviewerRole.approver, AppRoutes.activity),
      AppRoutes.home,
    );
    expect(_signedIn(ReviewerRole.auditor, AppRoutes.activity), isNull);
    expect(_signedIn(ReviewerRole.admin, AppRoutes.activity), isNull);
  });

  test('keeps auditors off approvals and their details', () {
    expect(
      _signedIn(ReviewerRole.auditor, AppRoutes.approvalDetails('apr_1')),
      AppRoutes.home,
    );
    expect(
      _signedIn(ReviewerRole.approver, AppRoutes.approvalDetails('apr_1')),
      isNull,
    );
  });

  test('waits while the session is unknown', () {
    expect(
      authRedirect(status: AuthStatus.unknown, location: AppRoutes.approvals),
      isNull,
    );
  });
}
