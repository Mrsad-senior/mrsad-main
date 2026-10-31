import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:go_router/go_router.dart';
import 'package:mirsad/core/di/injection.dart';
import 'package:mirsad/core/router/app_routes.dart';
import 'package:mirsad/core/router/app_shell.dart';
import 'package:mirsad/core/router/auth_redirect.dart';
import 'package:mirsad/core/router/stream_listenable.dart';
import 'package:mirsad/features/activity/presentation/cubit/activity_cubit.dart';
import 'package:mirsad/features/activity/presentation/pages/activity_page.dart';
import 'package:mirsad/features/approvals/presentation/cubit/approval_details_cubit.dart';
import 'package:mirsad/features/approvals/presentation/cubit/pending_approvals_cubit.dart';
import 'package:mirsad/features/approvals/presentation/pages/approval_details_page.dart';
import 'package:mirsad/features/approvals/presentation/pages/pending_approvals_page.dart';
import 'package:mirsad/features/audit/presentation/cubit/audit_cubit.dart';
import 'package:mirsad/features/audit/presentation/pages/audit_page.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:mirsad/features/auth/presentation/cubit/sign_in_cubit.dart';
import 'package:mirsad/features/auth/presentation/pages/sign_in_page.dart';

/// Builds the app's routes. Pages get their cubits here, from `getIt`.
/// Signed-out reviewers are sent to sign-in and back again afterwards.
GoRouter createAppRouter({
  required AuthCubit authCubit,
  required bool showMockSignInHint,
}) {
  final rootNavigatorKey = GlobalKey<NavigatorState>();
  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: AppRoutes.approvals,
    refreshListenable: StreamListenable(authCubit.stream),
    redirect: (context, state) => authRedirect(
      status: authCubit.state.status,
      location: state.matchedLocation,
    ),
    routes: [
      GoRoute(
        path: AppRoutes.signIn,
        builder: (context, state) => BlocProvider(
          create: (_) => getIt<SignInCubit>(),
          child: SignInPage(showMockHint: showMockSignInHint),
        ),
      ),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => AppShell(navigationShell: shell),
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.approvals,
                builder: (context, state) => BlocProvider(
                  create: (_) => getIt<PendingApprovalsCubit>()..start(),
                  child: const PendingApprovalsPage(),
                ),
                routes: [
                  GoRoute(
                    path: ':${AppRoutes.approvalIdParam}',
                    parentNavigatorKey: rootNavigatorKey,
                    builder: (context, state) {
                      final id =
                          state.pathParameters[AppRoutes.approvalIdParam]!;
                      return BlocProvider(
                        create: (_) {
                          final cubit = getIt<ApprovalDetailsCubit>();
                          unawaited(cubit.load(id));
                          return cubit;
                        },
                        child: const ApprovalDetailsPage(),
                      );
                    },
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.activity,
                builder: (context, state) => BlocProvider(
                  create: (_) => getIt<ActivityCubit>()..start(),
                  child: const ActivityPage(),
                ),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: AppRoutes.audit,
                builder: (context, state) => BlocProvider(
                  create: (_) {
                    final cubit = getIt<AuditCubit>();
                    unawaited(cubit.verify());
                    return cubit;
                  },
                  child: const AuditPage(),
                ),
              ),
            ],
          ),
        ],
      ),
    ],
  );
}
