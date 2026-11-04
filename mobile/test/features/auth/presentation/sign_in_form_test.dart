import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/auth/presentation/cubit/sign_in_cubit.dart';
import 'package:mirsad/features/auth/presentation/widgets/sign_in_form.dart';
import 'package:mocktail/mocktail.dart';

import '../../../helpers/pump_app.dart';

class _MockSignInCubit extends MockCubit<SignInState> implements SignInCubit {}

void main() {
  late _MockSignInCubit cubit;

  setUp(() {
    cubit = _MockSignInCubit();
    when(() => cubit.state).thenReturn(const SignInState());
    when(
      () => cubit.submit(
        username: any(named: 'username'),
        password: any(named: 'password'),
      ),
    ).thenAnswer((_) async {});
  });

  Future<void> pumpForm(WidgetTester tester, {Locale? locale}) {
    return tester.pumpApp(
      Scaffold(
        body: BlocProvider<SignInCubit>.value(
          value: cubit,
          child: const SignInForm(showMockHint: false),
        ),
      ),
      locale: locale ?? const Locale('en'),
    );
  }

  Future<void> fillIn(WidgetTester tester, String username, String password) {
    return tester
        .enterText(find.byType(TextFormField).first, username)
        .then(
          (_) => tester.enterText(find.byType(TextFormField).last, password),
        )
        .then((_) => tester.tap(find.byType(FilledButton)))
        .then((_) => tester.pump());
  }

  group('isValidUsername', () {
    test('accepts plain and email-style usernames', () {
      expect(SignInForm.isValidUsername('admin'), isTrue);
      expect(SignInForm.isValidUsername(' noura@bank.example '), isTrue);
    });

    test('rejects empty, spaced and over-long usernames', () {
      expect(SignInForm.isValidUsername(null), isFalse);
      expect(SignInForm.isValidUsername('   '), isFalse);
      expect(SignInForm.isValidUsername('nora q'), isFalse);
      expect(
        SignInForm.isValidUsername('a' * (SignInForm.maxUsernameLength + 1)),
        isFalse,
      );
    });
  });

  testWidgets('labels the field Username and signs in as "admin"', (
    tester,
  ) async {
    await pumpForm(tester);
    expect(find.text('Username'), findsOneWidget);

    // A short password is the gateway's business, not the form's.
    await fillIn(tester, 'admin', 'pw');

    verify(() => cubit.submit(username: 'admin', password: 'pw')).called(1);
  });

  testWidgets('explains what is wrong instead of submitting', (tester) async {
    await pumpForm(tester);

    await fillIn(tester, 'nora q', '');

    expect(find.text('Enter your username, without spaces.'), findsOneWidget);
    expect(find.text('Enter your password.'), findsOneWidget);
    verifyNever(
      () => cubit.submit(
        username: any(named: 'username'),
        password: any(named: 'password'),
      ),
    );
  });

  testWidgets('has Arabic labels', (tester) async {
    await pumpForm(tester, locale: const Locale('ar'));
    expect(find.text('اسم المستخدم'), findsOneWidget);
  });
}
