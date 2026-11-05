import 'package:mirsad/core/l10n/generated/app_localizations.dart';

/// A readable name for an agent tool, e.g. `transfer_funds` -> "Transfer
/// funds". Tools without a translation fall back to their name with
/// underscores turned into spaces.
String toolLabel(AppLocalizations l10n, String tool) {
  return switch (tool) {
    'transfer_funds' => l10n.toolTransferFunds,
    'send_email' => l10n.toolSendEmail,
    'export_customer_records' => l10n.toolExportCustomerRecords,
    'update_beneficiary' => l10n.toolUpdateBeneficiary,
    'get_account_balance' => l10n.toolGetAccountBalance,
    _ => humanizeIdentifier(tool),
  };
}

/// `some_tool_name` -> "Some tool name".
String humanizeIdentifier(String identifier) {
  final words = identifier.replaceAll(RegExp('[_-]+'), ' ').trim();
  if (words.isEmpty) return identifier;
  return words[0].toUpperCase() + words.substring(1);
}
