import 'package:flutter/widgets.dart';
import 'package:mirsad/core/l10n/generated/app_localizations.dart';

export 'package:mirsad/core/l10n/generated/app_localizations.dart';

extension L10nContext on BuildContext {
  AppLocalizations get l10n => AppLocalizations.of(this);
}
