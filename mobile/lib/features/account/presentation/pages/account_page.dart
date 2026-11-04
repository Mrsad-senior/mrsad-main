import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/widgets/error_state.dart';
import 'package:mirsad/core/widgets/language_toggle_button.dart';
import 'package:mirsad/core/widgets/section_card.dart';
import 'package:mirsad/features/account/presentation/cubit/account_cubit.dart';
import 'package:mirsad/features/account/presentation/widgets/account_header.dart';

/// Who is signed in, the app language and sign-out. Language and sign-out
/// stay available even when the gateway cannot be reached.
class AccountPage extends StatelessWidget {
  const AccountPage({required this.onSignOut, super.key});

  /// Signs the reviewer out. The router passes it in, because the session
  /// belongs to the auth feature.
  final VoidCallback onSignOut;

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final state = context.watch<AccountCubit>().state;
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        switch (state.status) {
          AccountStatus.loading => const Padding(
            padding: EdgeInsets.all(AppSpacing.xl),
            child: Center(child: CircularProgressIndicator()),
          ),
          AccountStatus.failure => ErrorState(
            message: state.failure!.localizedMessage(l10n),
            onRetry: context.read<AccountCubit>().load,
          ),
          AccountStatus.ready => AccountHeader(account: state.account!),
        },
        const SizedBox(height: AppSpacing.lg),
        SectionCard(
          title: l10n.accountLanguage,
          child: Row(
            children: [
              Expanded(child: Text(l10n.languageName)),
              const LanguageToggleButton(),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.xl),
        SizedBox(
          height: AppSizes.buttonHeight,
          child: FilledButton.tonalIcon(
            onPressed: onSignOut,
            icon: const Icon(Icons.logout),
            label: Text(l10n.signOut),
          ),
        ),
      ],
    );
  }
}
