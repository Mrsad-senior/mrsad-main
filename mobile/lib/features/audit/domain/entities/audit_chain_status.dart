import 'package:equatable/equatable.dart';

/// Whether the gateway's hash-chained audit log is intact.
class AuditChainStatus extends Equatable {
  const AuditChainStatus({required this.valid, this.brokenAt});

  const AuditChainStatus.intact() : this(valid: true);

  /// True when every entry matches its hash.
  final bool valid;

  /// The number of the first entry that fails verification, as stored by the
  /// gateway. Null when the chain is valid, or if the gateway did not say.
  final int? brokenAt;

  @override
  List<Object?> get props => [valid, brokenAt];
}
