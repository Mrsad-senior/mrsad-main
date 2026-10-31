import 'package:mirsad/features/audit/data/datasources/audit_data_source.dart';
import 'package:mirsad/features/audit/data/models/audit_chain_status_model.dart';

/// Reports an intact chain, or one broken at [brokenAt] to try that screen.
class AuditMockDataSource implements AuditDataSource {
  const AuditMockDataSource({
    this.brokenAt,
    this.latency = const Duration(milliseconds: 800),
  });

  final int? brokenAt;

  /// Simulated time to walk the chain.
  final Duration latency;

  @override
  Future<AuditChainStatusModel> verify() async {
    await Future<void>.delayed(latency);
    return AuditChainStatusModel(valid: brokenAt == null, brokenAt: brokenAt);
  }
}
