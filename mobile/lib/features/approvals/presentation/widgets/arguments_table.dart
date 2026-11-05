import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/core/theme/tokens/app_typography.dart';

/// The tool call's arguments exactly as the agent sent them.
class ArgumentsTable extends StatelessWidget {
  const ArgumentsTable({required this.arguments, super.key});

  final Map<String, Object?> arguments;

  /// How a raw argument value is shown: strings as-is, lists and maps as
  /// indented JSON.
  static String display(Object? value) {
    return switch (value) {
      null => 'null',
      String() => value,
      num() || bool() => value.toString(),
      _ => const JsonEncoder.withIndent('  ').convert(value),
    };
  }

  @override
  Widget build(BuildContext context) {
    final entries = arguments.entries.toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final (index, entry) in entries.indexed) ...[
          if (index > 0) const Divider(),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.key,
                  style: AppTypography.code.copyWith(
                    color: context.colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: AppSpacing.xxs),
                SelectableText(
                  display(entry.value),
                  style: context.textStyles.bodyMedium,
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}
