import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/features/auth/presentation/cubit/sign_in_cubit.dart';

class SignInForm extends StatefulWidget {
  const SignInForm({required this.showMockHint, super.key});

  /// The gateway's limit (`LoginRequest` in src/mirsad/api/schemas.py).
  static const maxUsernameLength = 128;

  /// Gateway usernames are plain names (`admin`) or email-style
  /// (`noura@bank.example`); neither has spaces.
  static bool isValidUsername(String? value) {
    final username = value?.trim() ?? '';
    return username.isNotEmpty &&
        username.length <= maxUsernameLength &&
        !username.contains(RegExp(r'\s'));
  }

  /// Explains that mock sign-in accepts anything.
  final bool showMockHint;

  @override
  State<SignInForm> createState() => _SignInFormState();
}

class _SignInFormState extends State<SignInForm> {
  final _formKey = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _password = TextEditingController();

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  void _submit() {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    context.read<SignInCubit>().submit(
      username: _username.text,
      password: _password.text,
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final state = context.watch<SignInCubit>().state;
    final failure = state.failure;
    return Form(
      key: _formKey,
      child: AutofillGroup(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _username,
              keyboardType: TextInputType.text,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.username],
              autocorrect: false,
              enableSuggestions: false,
              textDirection: TextDirection.ltr,
              decoration: InputDecoration(labelText: l10n.usernameLabel),
              validator: (value) => SignInForm.isValidUsername(value)
                  ? null
                  : l10n.usernameInvalid,
            ),
            const SizedBox(height: AppSpacing.lg),
            TextFormField(
              controller: _password,
              obscureText: true,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.password],
              decoration: InputDecoration(labelText: l10n.passwordLabel),
              onFieldSubmitted: (_) => _submit(),
              // The gateway decides whether the password is right; mock
              // sign-in checks its own minimum length.
              validator: (value) =>
                  (value?.isNotEmpty ?? false) ? null : l10n.passwordRequired,
            ),
            if (failure != null) ...[
              const SizedBox(height: AppSpacing.md),
              Text(
                failure.localizedMessage(l10n),
                style: context.textStyles.bodyMedium?.copyWith(
                  color: context.colors.error,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.xl),
            FilledButton(
              onPressed: state.isSubmitting ? null : _submit,
              child: state.isSubmitting
                  ? const SizedBox.square(
                      dimension: AppSizes.iconSm,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Text(l10n.signInButton),
            ),
            if (widget.showMockHint) ...[
              const SizedBox(height: AppSpacing.lg),
              Text(
                l10n.mockSignInHint,
                textAlign: TextAlign.center,
                style: context.textStyles.bodySmall?.copyWith(
                  color: context.colors.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
