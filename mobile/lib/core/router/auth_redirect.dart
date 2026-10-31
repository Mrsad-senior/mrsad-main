import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// Where to send someone at [location] given their sign-in [status], or null
/// to let them stay.
String? authRedirect({required AuthStatus status, required String location}) {
  final onSignIn = location == AppRoutes.signIn;
  return switch (status) {
    AuthStatus.unknown => null,
    AuthStatus.unauthenticated => onSignIn ? null : AppRoutes.signIn,
    AuthStatus.authenticated => onSignIn ? AppRoutes.approvals : null,
  };
}
