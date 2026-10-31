import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/app_theme.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/theme/tokens/app_typography.dart';

/// Shown instead of the app when the env file is unusable, so a bad build
/// says what is wrong instead of crashing.
class ConfigErrorApp extends StatelessWidget {
  const ConfigErrorApp({required this.problem, super.key});

  /// Developer-facing description of the problem.
  final String problem;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      home: Builder(
        builder: (context) => Scaffold(
          body: SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.settings_suggest_outlined,
                    size: AppSizes.iconLg,
                    color: context.colors.error,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Text(
                    context.l10n.configErrorTitle,
                    style: context.textStyles.titleLarge,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  SelectableText(
                    problem,
                    textAlign: TextAlign.center,
                    textDirection: TextDirection.ltr,
                    style: AppTypography.code,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
