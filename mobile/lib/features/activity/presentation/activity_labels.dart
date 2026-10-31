import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/widgets/status_badge.dart';
import 'package:mirsad/features/activity/domain/entities/gateway_decision.dart';

/// Display text, icon and color tone for a gateway decision.
extension GatewayDecisionDisplay on GatewayDecision {
  String label(AppLocalizations l10n) {
    return switch (this) {
      GatewayDecision.allowed => l10n.decisionAllowed,
      GatewayDecision.denied => l10n.decisionDenied,
      GatewayDecision.held => l10n.decisionHeld,
    };
  }

  IconData get icon {
    return switch (this) {
      GatewayDecision.allowed => Icons.check_circle_outline,
      GatewayDecision.denied => Icons.block,
      GatewayDecision.held => Icons.pause_circle_outline,
    };
  }

  StatusTone get tone {
    return switch (this) {
      GatewayDecision.allowed => StatusTone.positive,
      GatewayDecision.denied => StatusTone.negative,
      GatewayDecision.held => StatusTone.warning,
    };
  }
}
