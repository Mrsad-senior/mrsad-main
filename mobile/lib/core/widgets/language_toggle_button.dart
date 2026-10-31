import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/l10n/locale_cubit.dart';

/// Switches the app between English and Arabic. Labelled with the language
/// it switches to.
class LanguageToggleButton extends StatelessWidget {
  const LanguageToggleButton({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Tooltip(
      message: l10n.switchLanguage,
      child: TextButton(
        onPressed: () =>
            context.read<LocaleCubit>().toggle(Localizations.localeOf(context)),
        child: Text(l10n.otherLanguageName),
      ),
    );
  }
}
