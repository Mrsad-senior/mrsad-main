import 'package:flutter_test/flutter_test.dart';
import 'package:mirsad/core/l10n/generated/app_localizations_ar.dart';
import 'package:mirsad/core/l10n/generated/app_localizations_en.dart';
import 'package:mirsad/core/l10n/tool_labels.dart';

void main() {
  test('known tools use their translation', () {
    expect(toolLabel(AppLocalizationsEn(), 'transfer_funds'), 'Transfer funds');
    expect(toolLabel(AppLocalizationsAr(), 'transfer_funds'), 'تحويل أموال');
  });

  test('unknown tools fall back to a readable name', () {
    expect(toolLabel(AppLocalizationsEn(), 'freeze_card'), 'Freeze card');
    expect(humanizeIdentifier('lookup-fx_rate'), 'Lookup fx rate');
  });
}
