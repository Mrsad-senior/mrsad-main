import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/app.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/di/injection.dart';
import 'package:mirsad/core/router/app_router.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// Boots the real app in mock mode and walks the demo: sign in, see the
/// overview, then the held transfer, and open it.
void main() {
  Future<void> bootAndSignIn(WidgetTester tester, String username) async {
    await configureDependencies(
      const AppConfig(useMock: true, apiBaseUrl: 'http://10.0.2.2:8700'),
    );
    addTearDown(getIt.reset);
    final authCubit = getIt<AuthCubit>()..start();

    await tester.pumpWidget(
      MirsadApp(
        router: createAppRouter(authCubit: authCubit, showMockSignInHint: true),
        localeCubit: getIt(),
        authCubit: authCubit,
        clock: getIt(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Mock mode'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).first, username);
    await tester.enterText(find.byType(TextFormField).last, 'secret123');
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();
  }

  Finder tab(String label) => find.descendant(
    of: find.byType(NavigationBar),
    matching: find.text(label),
  );

  testWidgets('mock mode: sign in, then review the held transfer', (
    tester,
  ) async {
    await bootAndSignIn(tester, 'reviewer@bank.example');

    expect(find.text('Overview'), findsOneWidget);
    expect(find.text('Calls checked'), findsOneWidget);

    await tester.dragUntilVisible(
      find.text('Detector playground'),
      find.byType(ListView).first,
      const Offset(0, -300),
    );
    await tester.tap(find.text('Detector playground'));
    await tester.pumpAndSettle();
    expect(find.widgetWithText(FilledButton, 'Scan'), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(find.text('Demo chat'));
    await tester.pumpAndSettle();
    expect(find.text("The demo agent isn't enabled yet"), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();

    await tester.tap(tab('Approvals'));
    await tester.pumpAndSettle();
    expect(find.text('Pending approvals'), findsOneWidget);
    expect(find.text('Transfer funds'), findsOneWidget);
    expect(find.text('50,000 SAR'), findsOneWidget);
    expect(tab('Activity'), findsOneWidget);

    await tester.tap(find.text('Transfer funds'));
    await tester.pumpAndSettle();

    expect(find.text('Review action'), findsOneWidget);
    expect(find.text('Process this supplier invoice'), findsOneWidget);
  });

  testWidgets('an approver gets no Activity tab', (tester) async {
    await bootAndSignIn(tester, 'approver');

    expect(tab('Approvals'), findsOneWidget);
    expect(tab('Activity'), findsNothing);
    expect(tab('Audit'), findsOneWidget);
  });

  testWidgets('the Account tab shows the session and signs out', (
    tester,
  ) async {
    await bootAndSignIn(tester, 'approver');

    await tester.tap(tab('Account'));
    await tester.pumpAndSettle();
    expect(find.text('Approver'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Sign out'));
    await tester.pumpAndSettle();
    expect(find.byType(NavigationBar), findsNothing);
    expect(find.textContaining('Mock mode'), findsOneWidget);
  });

  testWidgets('an auditor gets no Approvals tab', (tester) async {
    await bootAndSignIn(tester, 'auditor');

    expect(tab('Home'), findsOneWidget);
    expect(tab('Approvals'), findsNothing);
    expect(tab('Activity'), findsOneWidget);
  });
}
