import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/approvals/domain/entities/approval.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/review_decision.dart';
import 'package:mirsad/features/approvals/presentation/cubit/approval_details_cubit.dart';
import 'package:mirsad/features/approvals/presentation/pages/approval_details_page.dart';
import 'package:mirsad/features/approvals/presentation/widgets/approval_details_body.dart';
import 'package:mirsad/features/approvals/presentation/widgets/decision_bar.dart';
import 'package:mirsad/features/approvals/presentation/widgets/decision_dialog.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fake_clock.dart';
import '../../../../helpers/pump_app.dart';
import '../../approval_fixtures.dart';
import '../../approvals_mocks.dart';

void main() {
  late MockApprovalDetailsCubit cubit;

  setUpAll(() => registerFallbackValue(ReviewDecision.approve));

  setUp(() => cubit = MockApprovalDetailsCubit());

  Future<void> pumpPage(
    WidgetTester tester, {
    Approval? approval,
    Locale locale = const Locale('en'),
  }) async {
    // Tall enough that the whole details list is built.
    tester.view
      ..physicalSize = const Size(1080, 2600)
      ..devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    whenListen(
      cubit,
      const Stream<ApprovalDetailsState>.empty(),
      initialState: ApprovalDetailsState(
        status: ApprovalDetailsStatus.ready,
        approval: approval ?? transferApproval(),
      ),
    );
    when(
      () => cubit.decide(any(), note: any(named: 'note')),
    ).thenAnswer((_) async {});

    await tester.pumpApp(
      BlocProvider<ApprovalDetailsCubit>.value(
        value: cubit,
        child: const ApprovalDetailsPage(),
      ),
      locale: locale,
      clock: FakeClock(testNow),
    );
  }

  testWidgets('sets the user task against what the agent is doing', (
    tester,
  ) async {
    await pumpPage(tester);

    expect(find.text('What the user asked'), findsOneWidget);
    expect(find.text('Process this supplier invoice'), findsOneWidget);
    expect(find.text('What the agent is trying to do'), findsOneWidget);
    expect(find.text('transfer_funds'), findsOneWidget);
    expect(find.text('50,000 SAR'), findsOneWidget);
    expect(find.text('To SA4420000001234567891234'), findsOneWidget);
  });

  testWidgets('lists the arguments and every layer reason', (tester) async {
    await pumpPage(tester);

    expect(find.text('to_iban'), findsOneWidget);
    expect(find.text('reference'), findsOneWidget);
    expect(find.text('Intent check'), findsOneWidget);
    expect(
      find.text('The user asked to process an invoice, not to pay a new IBAN.'),
      findsOneWidget,
    );
    expect(find.text('LLM judge'), findsOneWidget);
    expect(find.text('Auto-rejects in 4:20'), findsOneWidget);
  });

  testWidgets('reject asks for confirmation and sends the note', (
    tester,
  ) async {
    await pumpPage(tester);

    await tester.tap(find.byKey(DecisionBar.rejectKey));
    await tester.pumpAndSettle();
    expect(find.text('Reject this action?'), findsOneWidget);

    await tester.enterText(
      find.byKey(DecisionDialog.noteFieldKey),
      'IBAN is not on the supplier record',
    );
    await tester.tap(find.byKey(DecisionDialog.confirmKey));
    await tester.pumpAndSettle();

    verify(
      () => cubit.decide(
        ReviewDecision.reject,
        note: 'IBAN is not on the supplier record',
      ),
    ).called(1);
  });

  testWidgets('cancelling the confirmation sends nothing', (tester) async {
    await pumpPage(tester);

    await tester.tap(find.byKey(DecisionBar.approveKey));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();

    verifyNever(() => cubit.decide(any(), note: any(named: 'note')));
  });

  testWidgets('turns the buttons off once the time is up', (tester) async {
    await pumpPage(tester, approval: transferApproval(expiresAt: testNow));

    final reject = tester.widget<FilledButton>(
      find.byKey(DecisionBar.rejectKey),
    );
    expect(reject.onPressed, isNull);
    expect(find.text('Expired'), findsOneWidget);
  });

  testWidgets('hides the buttons when the action is no longer held', (
    tester,
  ) async {
    await pumpPage(
      tester,
      approval: transferApproval(status: ApprovalStatus.rejected),
    );

    expect(find.byKey(DecisionBar.rejectKey), findsNothing);
    expect(find.text('Rejected'), findsOneWidget);
  });

  testWidgets('lays out right to left in Arabic', (tester) async {
    await pumpPage(tester, locale: const Locale('ar'));

    final body = tester.element(find.byType(ApprovalDetailsBody));
    expect(Directionality.of(body), TextDirection.rtl);
    expect(find.text('ما طلبه المستخدم'), findsOneWidget);
    expect(find.text('رفض'), findsOneWidget);
  });
}
