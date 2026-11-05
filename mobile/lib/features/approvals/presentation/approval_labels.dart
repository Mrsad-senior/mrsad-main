import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/approvals/domain/entities/approval_status.dart';
import 'package:mirsad/features/approvals/domain/entities/reason_layer.dart';
import 'package:mirsad/features/approvals/domain/entities/sector.dart';

/// Display text, icons and tones for the approval enums.
extension ApprovalStatusDisplay on ApprovalStatus {
  String label(AppLocalizations l10n) {
    return switch (this) {
      ApprovalStatus.held => l10n.statusHeld,
      ApprovalStatus.approved => l10n.statusApproved,
      ApprovalStatus.rejected => l10n.statusRejected,
      ApprovalStatus.expired => l10n.statusExpired,
    };
  }

  StatusTone get tone {
    return switch (this) {
      ApprovalStatus.held => StatusTone.warning,
      ApprovalStatus.approved => StatusTone.positive,
      ApprovalStatus.rejected => StatusTone.negative,
      ApprovalStatus.expired => StatusTone.neutral,
    };
  }
}

extension ReasonLayerDisplay on ReasonLayer {
  String label(AppLocalizations l10n) {
    return switch (this) {
      ReasonLayer.policy => l10n.layerPolicy,
      ReasonLayer.taint => l10n.layerTaint,
      ReasonLayer.intent => l10n.layerIntent,
      ReasonLayer.llmJudge => l10n.layerLlmJudge,
      ReasonLayer.keywords => l10n.layerKeywords,
      ReasonLayer.other => l10n.layerOther,
    };
  }

  IconData get icon {
    return switch (this) {
      ReasonLayer.policy => Icons.policy_outlined,
      ReasonLayer.taint => Icons.coronavirus_outlined,
      ReasonLayer.intent => Icons.track_changes,
      ReasonLayer.llmJudge => Icons.psychology_outlined,
      ReasonLayer.keywords => Icons.manage_search,
      ReasonLayer.other => Icons.rule,
    };
  }
}

extension SectorDisplay on Sector {
  String label(AppLocalizations l10n) {
    return switch (this) {
      Sector.finance => l10n.sectorFinance,
      Sector.healthcare => l10n.sectorHealthcare,
      Sector.general => l10n.sectorGeneral,
    };
  }
}

/// "50,000 SAR", formatted for the current language.
String formatAmount(BuildContext context, num amount, String? currency) {
  final locale = Localizations.localeOf(context).toLanguageTag();
  final number = NumberFormat.decimalPattern(locale).format(amount);
  return currency == null ? number : '$number $currency';
}

/// "4:07" for a countdown.
String formatCountdown(Duration remaining) {
  final seconds = (remaining.inSeconds % 60).toString().padLeft(2, '0');
  return '${remaining.inMinutes}:$seconds';
}
