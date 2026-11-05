import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mirsad/core/utils/clock.dart';

/// Rebuilds once a second with the time left until [expiresAt], and stops at
/// zero. Reads the time from the [Clock] in context.
class ExpiryTicker extends StatefulWidget {
  const ExpiryTicker({
    required this.expiresAt,
    required this.builder,
    super.key,
  });

  final DateTime expiresAt;
  final Widget Function(BuildContext context, Duration remaining) builder;

  @override
  State<ExpiryTicker> createState() => _ExpiryTickerState();
}

class _ExpiryTickerState extends State<ExpiryTicker> {
  late final Clock _clock = context.read<Clock>();
  late Duration _remaining;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _restart();
  }

  @override
  void didUpdateWidget(ExpiryTicker oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.expiresAt != widget.expiresAt) _restart();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _restart() {
    _timer?.cancel();
    _remaining = _timeLeft();
    if (_remaining > Duration.zero) {
      _timer = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
    }
  }

  void _tick() {
    final next = _timeLeft();
    if (next.inSeconds != _remaining.inSeconds) {
      setState(() => _remaining = next);
    }
    if (next == Duration.zero) _timer?.cancel();
  }

  Duration _timeLeft() {
    final left = widget.expiresAt.difference(_clock.now());
    return left.isNegative ? Duration.zero : left;
  }

  @override
  Widget build(BuildContext context) => widget.builder(context, _remaining);
}
