import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/home/presentation/cubit/home_cubit.dart';
import 'package:mirsad/features/home/presentation/pages/home_page.dart';

import '../../../../helpers/pump_app.dart';
import '../../home_fixtures.dart';
import '../../home_mocks.dart';

void main() {
  late MockHomeCubit cubit;

  setUp(() => cubit = MockHomeCubit());

  Future<void> pumpPage(
    WidgetTester tester, {
    bool showDetector = true,
    Locale locale = const Locale('en'),
  }) async {
    tester.view
      ..physicalSize = const Size(1080, 3000)
      ..devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    whenListen(
      cubit,
      const Stream<HomeState>.empty(),
      initialState: const HomeState(
        status: HomeStatus.ready,
        stats: overviewStats,
      ),
    );
    await tester.pumpApp(
      Scaffold(
        body: BlocProvider<HomeCubit>.value(
          value: cubit,
          child: HomePage(showDetector: showDetector),
        ),
      ),
      locale: locale,
    );
  }

  testWidgets('shows the last 24 hours', (tester) async {
    await pumpPage(tester);

    expect(find.text('Last 24 hours'), findsOneWidget);
    expect(find.text('Calls checked'), findsOneWidget);
    expect(find.text('14'), findsOneWidget);
    expect(find.text('Audit chain intact'), findsOneWidget);
    expect(find.text('Decides in 0.2 ms (p95 0.2 ms)'), findsOneWidget);
    expect(find.text('Check balance'), findsOneWidget);
  });

  testWidgets('links to the detector and the chat', (tester) async {
    await pumpPage(tester);
    expect(find.text('Detector playground'), findsOneWidget);
    expect(find.text('Demo chat'), findsOneWidget);
  });

  testWidgets('hides the detector from roles that cannot use it', (
    tester,
  ) async {
    await pumpPage(tester, showDetector: false);
    expect(find.text('Detector playground'), findsNothing);
    expect(find.text('Demo chat'), findsOneWidget);
  });

  testWidgets('reads in Arabic', (tester) async {
    await pumpPage(tester, locale: const Locale('ar'));
    expect(find.text('سلسلة التدقيق سليمة'), findsOneWidget);
  });
}
