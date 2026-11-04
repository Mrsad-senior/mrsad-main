import 'package:flutter/material.dart';
import 'package:mirsad/core/l10n/l10n.dart';
import 'package:mirsad/core/widgets/empty_state.dart';

/// A placeholder for chatting with the demo agent. The gateway only mounts
/// `/api/demo/chat` when `MIRSAD_ENABLE_DEMO=true`, and the hosted gateway
/// runs without it, so there is nothing to call yet. Once it is enabled,
/// this becomes a feature with its own domain and data layers.
class ChatPage extends StatelessWidget {
  const ChatPage({super.key});

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.chatTitle)),
      body: EmptyState(
        icon: Icons.chat_bubble_outline,
        title: l10n.chatNotEnabledTitle,
        message: l10n.chatNotEnabledMessage,
      ),
    );
  }
}
