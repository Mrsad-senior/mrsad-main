import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/core/router/auth_redirect.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

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

  test('sends signed-in reviewers from sign-in to their approvals', () {
    expect(
      authRedirect(
        status: AuthStatus.authenticated,
        location: AppRoutes.signIn,
      ),
      AppRoutes.approvals,
    );
    expect(
      authRedirect(status: AuthStatus.authenticated, location: AppRoutes.audit),
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
