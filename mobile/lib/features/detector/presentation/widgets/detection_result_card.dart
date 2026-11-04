import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/section_card.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/detector/domain/entities/detection_label.dart';
import 'package:mirsad/features/detector/domain/entities/detection_language.dart';
import 'package:mirsad/features/detector/domain/entities/detection_result.dart';

/// The verdict, score, language, signals and flagged passages of one scan.
class DetectionResultCard extends StatelessWidget {
  const DetectionResultCard({required this.result, super.key});

  final DetectionResult result;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final locale = Localizations.localeOf(context).toLanguageTag();
    final (label, tone, icon) = switch (result.label) {
      DetectionLabel.benign => (
        l10n.detectorLabelBenign,
        StatusTone.positive,
        Icons.check_circle_outline,
      ),
      DetectionLabel.suspicious => (
        l10n.detectorLabelSuspicious,
        StatusTone.warning,
        Icons.help_outline,
      ),
      DetectionLabel.injection => (
        l10n.detectorLabelInjection,
        StatusTone.negative,
        Icons.gpp_bad_outlined,
      ),
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            StatusBadge(label: label, tone: tone, icon: icon),
            StatusBadge(
              label: l10n.detectorScore(
                NumberFormat('0.00', locale).format(result.score),
              ),
              tone: StatusTone.neutral,
            ),
            StatusBadge(
              label: _languageLabel(l10n, result.language),
              tone: StatusTone.neutral,
              icon: Icons.translate,
            ),
          ],
        ),
        if (result.signals.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.lg),
          SectionCard(
            title: l10n.detectorSignals,
            child: Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                for (final signal in result.signals) Chip(label: Text(signal)),
              ],
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.lg),
        SectionCard(
          title: l10n.detectorSpans,
          child: result.spans.isEmpty
              ? Text(l10n.detectorNoSpans)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final span in result.spans)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: const Icon(Icons.format_quote),
                        title: Text(span.text),
                        subtitle: span.ruleId == null
                            ? null
                            : Text(
                                span.ruleId!,
                                style: context.textStyles.bodySmall?.copyWith(
                                  color: context.colors.onSurfaceVariant,
                                ),
                              ),
                      ),
                  ],
                ),
        ),
      ],
    );
  }

  static String _languageLabel(
    AppLocalizations l10n,
    DetectionLanguage language,
  ) {
    return switch (language) {
      DetectionLanguage.en => l10n.detectorLanguageEn,
      DetectionLanguage.ar => l10n.detectorLanguageAr,
      DetectionLanguage.mixed => l10n.detectorLanguageMixed,
      DetectionLanguage.other => l10n.detectorLanguageOther,
    };
  }
}
