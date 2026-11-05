import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/l10n/failure_messages.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/theme/theme_context.dart';
import 'package:mirsad/core/theme/tokens/app_sizes.dart';
import 'package:mirsad/core/theme/tokens/app_spacing.dart';
import 'package:mirsad/features/detector/domain/usecases/scan_text.dart';
import 'package:mirsad/features/detector/presentation/cubit/detector_cubit.dart';
import 'package:mirsad/features/detector/presentation/widgets/detection_result_card.dart';

/// Paste a text and see how the gateway's prompt-injection detector scores
/// it.
class DetectorPage extends StatefulWidget {
  const DetectorPage({super.key});

  @override
  State<DetectorPage> createState() => _DetectorPageState();
}

class _DetectorPageState extends State<DetectorPage> {
  final _text = TextEditingController();

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  void _scan() {
    FocusScope.of(context).unfocus();
    context.read<DetectorCubit>().scan(_text.text);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    final state = context.watch<DetectorCubit>().state;
    final scanning = state.status == DetectorStatus.scanning;
    final result = state.result;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.detectorTitle)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          Text(
            l10n.detectorHint,
            style: context.textStyles.bodyMedium?.copyWith(
              color: context.colors.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          TextField(
            controller: _text,
            minLines: 5,
            maxLines: 12,
            maxLength: ScanText.maxLength,
            keyboardType: TextInputType.multiline,
            decoration: InputDecoration(
              labelText: l10n.detectorInputLabel,
              alignLabelWithHint: true,
              counterText: '',
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          ListenableBuilder(
            listenable: _text,
            builder: (context, _) => SizedBox(
              height: AppSizes.buttonHeight,
              child: FilledButton.icon(
                onPressed: scanning || _text.text.trim().isEmpty ? null : _scan,
                icon: scanning
                    ? const SizedBox.square(
                        dimension: AppSizes.iconSm,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.manage_search),
                label: Text(l10n.detectorScan),
              ),
            ),
          ),
          if (state.status == DetectorStatus.failure) ...[
            const SizedBox(height: AppSpacing.lg),
            Text(
              state.failure!.localizedMessage(l10n),
              style: context.textStyles.bodyMedium?.copyWith(
                color: context.colors.error,
              ),
            ),
          ],
          if (result != null) ...[
            const SizedBox(height: AppSpacing.xl),
            DetectionResultCard(result: result),
          ],
        ],
      ),
    );
  }
}
