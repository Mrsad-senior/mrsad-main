import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/di/live_session.dart';
import 'package:mirsad/core/network/live/live_status_cubit.dart';
import 'package:mirsad/core/network/live/live_updates.dart';
import 'package:mirsad/core/widgets/live_status_indicator.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

import '../../../features/auth/auth_mocks.dart';
import '../../../helpers/fake_live_updates.dart';
import '../../../helpers/pump_app.dart';

class _MockAuthCubit extends MockCubit<AuthState> implements AuthCubit {}

void main() {
  late FakeLiveUpdates live;

  setUp(() => live = FakeLiveUpdates(status: LiveStatus.connecting));

  tearDown(() => live.close());

  group('LiveStatusCubit', () {
    blocTest<LiveStatusCubit, LiveStatus>(
      'starts from the current status and follows changes',
      build: () => LiveStatusCubit(live),
      act: (_) => live
        ..setStatus(LiveStatus.online)
        ..setStatus(LiveStatus.reconnecting),
      verify: (cubit) => expect(cubit.state, LiveStatus.reconnecting),
      expect: () => [LiveStatus.online, LiveStatus.reconnecting],
    );
  });

  group('LiveStatusIndicator', () {
    Future<void> pump(WidgetTester tester, LiveStatus status) {
      return tester.pumpApp(
        Scaffold(
          body: BlocProvider(
            create: (_) => LiveStatusCubit(FakeLiveUpdates(status: status)),
            child: const LiveStatusIndicator(),
          ),
        ),
      );
    }

    testWidgets('says Online while connected', (tester) async {
      await pump(tester, LiveStatus.online);
      expect(find.text('Online'), findsOneWidget);
    });

    testWidgets('says Reconnecting while retrying', (tester) async {
      await pump(tester, LiveStatus.reconnecting);
      expect(find.text('Reconnecting…'), findsOneWidget);
    });

    testWidgets('shows nothing while signed out', (tester) async {
      await pump(tester, LiveStatus.offline);
      expect(find.byType(Text), findsNothing);
    });
  });

  test('the stream is open exactly while someone is signed in', () async {
    final auth = _MockAuthCubit();
    whenListen(
      auth,
      Stream.fromIterable(const [
        AuthState.unauthenticated(),
        AuthState.authenticated(reviewer),
        AuthState.unauthenticated(),
      ]),
      initialState: const AuthState.authenticated(reviewer),
    );

    final subscription = connectLiveUpdatesToSession(auth: auth, live: live);
    await settle();

    expect(live.starts, 2);
    expect(live.stops, 2);
    await subscription.cancel();
  });
}
