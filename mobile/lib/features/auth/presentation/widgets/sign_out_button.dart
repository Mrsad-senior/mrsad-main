import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/features/auth/presentation/cubit/auth_cubit.dart';

class SignOutButton extends StatelessWidget {
  const SignOutButton({super.key});

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: context.l10n.signOut,
      icon: const Icon(Icons.logout),
      onPressed: () => context.read<AuthCubit>().signOut(),
    );
  }
}
