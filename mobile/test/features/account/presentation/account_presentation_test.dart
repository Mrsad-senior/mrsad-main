import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/core/errors/failure.dart';
import 'package:mirsad/core/l10n/locale_cubit.dart';
import 'package:mirsad/features/account/presentation/cubit/account_cubit.dart';
import 'package:mirsad/features/account/presentation/pages/account_page.dart';
import 'package:mocktail/mocktail.dart';

import '../../../helpers/pump_app.dart';
import '../account_mocks.dart';

void main() {
  group('AccountCubit', () {
    late MockGetAccount getAccount;

    setUp(() => getAccount = MockGetAccount());

    blocTest<AccountCubit, AccountState>(
      'loads the account',
      setUp: () =>
          when(() => getAccount()).thenAnswer((_) async => const Right(noura)),
      build: () => AccountCubit(getAccount: getAccount),
      act: (cubit) => cubit.load(),
      expect: () => const [
        AccountState(),
        AccountState(status: AccountStatus.ready, account: noura),
      ],
    );

    blocTest<AccountCubit, AccountState>(
      'shows why it could not load',
      setUp: () => when(
        () => getAccount(),
      ).thenAnswer((_) async => const Left(NetworkFailure())),
      build: () => AccountCubit(getAccount: getAccount),
      act: (cubit) => cubit.load(),
      expect: () => const [
        AccountState(),
        AccountState(status: AccountStatus.failure, failure: NetworkFailure()),
      ],
    );
  });

  group('AccountPage', () {
    late MockAccountCubit cubit;
    late LocaleCubit localeCubit;
    late int signOuts;

    setUp(() {
      cubit = MockAccountCubit();
      localeCubit = LocaleCubit();
      signOuts = 0;
    });

    tearDown(() => localeCubit.close());

    Future<void> pumpPage(WidgetTester tester, AccountState state) {
      whenListen(
        cubit,
        const Stream<AccountState>.empty(),
        initialState: state,
      );
      return tester.pumpApp(
        Scaffold(
          body: MultiBlocProvider(
            providers: [
              BlocProvider<AccountCubit>.value(value: cubit),
              BlocProvider<LocaleCubit>.value(value: localeCubit),
            ],
            child: AccountPage(onSignOut: () => signOuts++),
          ),
        ),
      );
    }

    testWidgets('shows the account and signs out', (tester) async {
      await pumpPage(
        tester,
        const AccountState(status: AccountStatus.ready, account: noura),
      );

      expect(find.text('Noura'), findsOneWidget);
      expect(find.text('noura@bank.example'), findsOneWidget);
      expect(find.text('Approver'), findsOneWidget);
      expect(find.text('English'), findsOneWidget);

      await tester.tap(find.text('Sign out'));
      expect(signOuts, 1);
    });

    testWidgets('switches the language', (tester) async {
      await pumpPage(
        tester,
        const AccountState(status: AccountStatus.ready, account: noura),
      );

      await tester.tap(find.text('العربية'));
      expect(localeCubit.state, LocaleCubit.arabic);
    });

    testWidgets('can still sign out when the account fails to load', (
      tester,
    ) async {
      await pumpPage(
        tester,
        const AccountState(
          status: AccountStatus.failure,
          failure: NetworkFailure(),
        ),
      );

      expect(find.text('Try again'), findsOneWidget);
      await tester.tap(find.text('Sign out'));
      expect(signOuts, 1);
    });
  });
}
