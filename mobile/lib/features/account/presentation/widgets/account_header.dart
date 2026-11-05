import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/section_card.dart';
import 'package:mirsad/features/account/domain/entities/account.dart';

/// The account's name, username and role.
class AccountHeader extends StatelessWidget {
  const AccountHeader({required this.account, super.key});

  final Account account;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final name = account.name;
    return SectionCard(
      title: l10n.accountTitle,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: CircleAvatar(
              child: Text(name.isEmpty ? '?' : name[0].toUpperCase()),
            ),
            title: Text(name, style: context.textStyles.titleMedium),
            subtitle: name == account.username
                ? null
                : Text(account.username, textDirection: TextDirection.ltr),
          ),
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: [
              Text(
                l10n.accountRole,
                style: context.textStyles.bodyMedium?.copyWith(
                  color: context.colors.onSurfaceVariant,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Text(
                _roleLabel(l10n, account.role),
                style: context.textStyles.bodyLarge,
              ),
            ],
          ),
        ],
      ),
    );
  }

  static String _roleLabel(AppLocalizations l10n, String role) {
    return switch (role) {
      'admin' => l10n.roleAdmin,
      'approver' => l10n.roleApprover,
      'auditor' => l10n.roleAuditor,
      _ => role,
    };
  }
}
