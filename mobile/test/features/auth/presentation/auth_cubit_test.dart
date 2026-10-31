import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:mirsad/features/auth/domain/entities/reviewer.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';
import 'package:mocktail/mocktail.dart';

import '../auth_mocks.dart';

void main() {
  late MockGetCurrentReviewer getCurrentReviewer;
  late MockWatchReviewer watchReviewer;
  late MockSignOut signOut;
  late StreamController<Reviewer?> changes;

  setUp(() {
    getCurrentReviewer = MockGetCurrentReviewer();
    watchReviewer = MockWatchReviewer();
    signOut = MockSignOut();
    changes = StreamController.broadcast();
    when(() => watchReviewer()).thenAnswer((_) => changes.stream);
    when(() => getCurrentReviewer()).thenReturn(null);
  });

  tearDown(() => changes.close());

  AuthCubit build() => AuthCubit(
    getCurrentReviewer: getCurrentReviewer,
    watchReviewer: watchReviewer,
    signOut: signOut,
  );

  test('does not know the session before start', () {
    expect(build().state, const AuthState.unknown());
  });

  blocTest<AuthCubit, AuthState>(
    'start reports the existing session right away',
    setUp: () => when(() => getCurrentReviewer()).thenReturn(reviewer),
    build: build,
    act: (cubit) => cubit.start(),
    expect: () => const [AuthState.authenticated(reviewer)],
  );

  blocTest<AuthCubit, AuthState>(
    'follows sign-ins and sign-outs',
    build: build,
    act: (cubit) {
      cubit.start();
      changes
        ..add(reviewer)
        ..add(null);
    },
    expect: () => const [
      AuthState.unauthenticated(),
      AuthState.authenticated(reviewer),
      AuthState.unauthenticated(),
    ],
  );

  blocTest<AuthCubit, AuthState>(
    'signOut calls the use case',
    setUp: () =>
        when(() => signOut()).thenAnswer((_) async => const Right(unit)),
    build: build,
    act: (cubit) => cubit.signOut(),
    verify: (_) => verify(() => signOut()).called(1),
  );
}
