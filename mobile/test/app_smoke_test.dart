import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/app.dart';
import 'package:mirsad/core/config/app_config.dart';
import 'package:mirsad/core/di/injection.dart';
import 'package:mirsad/core/router/app_router.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

/// Boots the real app in mock mode and walks the demo: sign in, see the held
/// transfer, open it.
void main() {
  testWidgets('mock mode: sign in, then review the held transfer', (
    tester,
  ) async {
    await configureDependencies(
      const AppConfig(
        useMock: true,
        readSource: ReadSource.supabase,
        apiBaseUrl: 'http://10.0.2.2:8000',
        supabaseUrl: '',
        supabaseAnonKey: '',
      ),
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
    await tester.enterText(
      find.byType(TextFormField).first,
      'reviewer@bank.example',
    );
    await tester.enterText(find.byType(TextFormField).last, 'secret123');
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.text('Pending approvals'), findsOneWidget);
    expect(find.text('Transfer funds'), findsOneWidget);
    expect(find.text('50,000 SAR'), findsOneWidget);

    await tester.tap(find.text('Transfer funds'));
    await tester.pumpAndSettle();

    expect(find.text('Review action'), findsOneWidget);
    expect(find.text('Process this supplier invoice'), findsOneWidget);
  });
}
