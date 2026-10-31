import 'package:flutter/material.dart';

/// Centers [child] in a scroll view that always scrolls, so pull-to-refresh
/// still works when a list is empty or failed to load.
class FillScrollView extends StatelessWidget {
  const FillScrollView({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [SliverFillRemaining(hasScrollBody: false, child: child)],
    );
  }
}
