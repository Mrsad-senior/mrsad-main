import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/features/chat/presentation/pages/chat_page.dart';

import '../../helpers/pump_app.dart';

void main() {
  testWidgets('says the demo agent is not enabled yet', (tester) async {
    await tester.pumpApp(const ChatPage());

    expect(find.text('Demo chat'), findsOneWidget);
    expect(find.text("The demo agent isn't enabled yet"), findsOneWidget);
    expect(find.textContaining('MIRSAD_ENABLE_DEMO'), findsOneWidget);
  });

  testWidgets('in Arabic too', (tester) async {
    await tester.pumpApp(const ChatPage(), locale: const Locale('ar'));
    expect(find.text('الوكيل التجريبي غير مفعّل بعد'), findsOneWidget);
  });
}
