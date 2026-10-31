import 'package:flutter/material.dart';

/// The icon for an agent tool. Unknown tools get a generic one.
IconData toolIcon(String tool) {
  return switch (tool) {
    'transfer_funds' => Icons.payments_outlined,
    'send_email' => Icons.mail_outline,
    'export_customer_records' => Icons.file_download_outlined,
    'update_beneficiary' => Icons.manage_accounts_outlined,
    'get_account_balance' => Icons.account_balance_wallet_outlined,
    _ => Icons.build_outlined,
  };
}
